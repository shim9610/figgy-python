//! Standalone production radial pass: no Python, WASM, browser, UI or screenshot.
use renderer::{Color, RendererDevice, radial::*};
use serde_json::{Value, json};
use std::{
    error::Error,
    fs::File,
    io::Write,
    sync::Arc,
    time::{Duration, Instant},
};

type Result<T> = std::result::Result<T, Box<dyn Error>>;

fn wait(device: &wgpu::Device) -> Result<()> {
    device.poll(wgpu::PollType::Wait {
        submission_index: None,
        timeout: Some(Duration::from_secs(180)),
    })?;
    Ok(())
}

fn main() -> Result<()> {
    let args: Vec<String> = std::env::args().collect();
    let option = |name: &str, default: &str| -> String {
        args.windows(2)
            .find(|a| a[0] == name)
            .map(|a| a[1].clone())
            .unwrap_or_else(|| default.into())
    };
    if args.iter().any(|a| a == "--help") {
        println!(
            "--output FILE (required, must not exist) --cases 480x300:3,960x600:3,480x300:12 --frames 3 --no-queries"
        );
        return Ok(());
    }
    let output = option("--output", "");
    if output.is_empty() {
        return Err("--output is required".into());
    }
    let mut file = File::create_new(output)?;
    let frames: usize = option("--frames", "3").parse()?;
    if frames < 2 {
        return Err("at least two frames are required to separate cold and warm work".into());
    }
    let cases = option("--cases", "480x300:3,960x600:3,480x300:12");
    let instance = wgpu::Instance::new(wgpu::InstanceDescriptor {
        backends: wgpu::Backends::VULKAN,
        ..wgpu::InstanceDescriptor::new_without_display_handle()
    });
    let adapter =
        pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions::default()))?;
    let info = adapter.get_info();
    let available = adapter.features();
    let requested = if args.iter().any(|a| a == "--no-queries") {
        wgpu::Features::empty()
    } else {
        available & (wgpu::Features::TIMESTAMP_QUERY | wgpu::Features::PIPELINE_STATISTICS_QUERY)
    };
    let (device, queue) = pollster::block_on(adapter.request_device(&wgpu::DeviceDescriptor {
        label: Some("independent radial measurement"),
        required_features: requested,
        required_limits: wgpu::Limits::default(),
        experimental_features: wgpu::ExperimentalFeatures::disabled(),
        memory_hints: wgpu::MemoryHints::Performance,
        trace: wgpu::Trace::Off,
    }))?;
    let device = Arc::new(device);
    let queue = Arc::new(queue);
    let gpu = RendererDevice::new(device.clone(), queue.clone());
    let started = Instant::now();
    let mut renderer = RadialRenderer::new(gpu, wgpu::TextureFormat::Rgba8Unorm)?;
    let pipeline_cpu_ms = started.elapsed().as_secs_f64() * 1000.;
    let timestamp = requested
        .contains(wgpu::Features::TIMESTAMP_QUERY)
        .then(|| {
            device.create_query_set(&wgpu::QuerySetDescriptor {
                label: Some("radial pass timestamps"),
                ty: wgpu::QueryType::Timestamp,
                count: 2,
            })
        });
    let statistics = requested
        .contains(wgpu::Features::PIPELINE_STATISTICS_QUERY)
        .then(|| {
            device.create_query_set(&wgpu::QuerySetDescriptor {
                label: Some("radial fragment invocations"),
                ty: wgpu::QueryType::PipelineStatistics(
                    wgpu::PipelineStatisticsTypes::FRAGMENT_SHADER_INVOCATIONS,
                ),
                count: 1,
            })
        });
    let resolve = device.create_buffer(&wgpu::BufferDescriptor {
        label: Some("query resolve"),
        size: 512,
        usage: wgpu::BufferUsages::QUERY_RESOLVE | wgpu::BufferUsages::COPY_SRC,
        mapped_at_creation: false,
    });
    let readback = device.create_buffer(&wgpu::BufferDescriptor {
        label: Some("query readback"),
        size: 512,
        usage: wgpu::BufferUsages::MAP_READ | wgpu::BufferUsages::COPY_DST,
        mapped_at_creation: false,
    });
    let metadata = json!({"type":"environment", "renderer":"0.18.0", "wgpu":"30.0.1",
        "adapter":format!("{info:?}"), "available_features":format!("{available:?}"),
        "timestamp_query":timestamp.is_some(), "pipeline_statistics_query":statistics.is_some(),
        "timestamp_period_ns":queue.get_timestamp_period(), "pipeline_cpu_ms":pipeline_cpu_ms,
        "vk_driver_files":std::env::var("VK_DRIVER_FILES").ok(),
        "logical_cpus":std::thread::available_parallelism()?.get(),
        "cpu_quota":std::fs::read_to_string("/sys/fs/cgroup/cpu.max").ok(),
        "style":"Flat, zero depth/tilt, no shadows/outlines, fixed data, no hover",
        "work_definition":"logical pixels * 4 AA samples * slices main-loop hit_pixel calls; not FLOPs or machine instructions"});
    emit(&mut file, &metadata)?;
    for case in cases.split(',') {
        let (size, count) = case.split_once(':').ok_or("expected WIDTHxHEIGHT:SLICES")?;
        let (w, h) = size.split_once('x').ok_or("expected WIDTHxHEIGHT")?;
        let (width, height, count): (u32, u32, usize) = (w.parse()?, h.parse()?, count.parse()?);
        if count == 0 {
            return Err("slice count must be nonzero".into());
        }
        let mut chart = RadialChart {
            kind: RadialKind::Donut { inner_radius: 0.5 },
            labels: RadialLabels::None,
            slices: (0..count)
                .map(|i| {
                    RadialSlice::new(
                        "",
                        (i % 3 + 2) as f64,
                        Color::from_rgb8(50 + (i % 3) as u8 * 60, 100, 180),
                    )
                })
                .collect(),
            ..Default::default()
        };
        chart.style.material = RadialMaterial::Flat;
        chart.style.depth = 0.;
        chart.style.tilt_degrees = 0.;
        chart.style.shadow = false;
        chart.style.outline.rim = false;
        chart.style.outline.separators = false;
        chart.style.outline.emphasis = false;
        let start = Instant::now();
        let frame = renderer.prepare(&chart, (width, height), 1.)?;
        wait(&device)?; // Preparation/annotation uploads are outside measured passes.
        let prepare_ms = start.elapsed().as_secs_f64() * 1000.;
        let texture = device.create_texture(&wgpu::TextureDescriptor {
            label: Some("radial benchmark target"),
            size: wgpu::Extent3d {
                width,
                height,
                depth_or_array_layers: 1,
            },
            mip_level_count: 1,
            sample_count: 1,
            dimension: wgpu::TextureDimension::D2,
            format: wgpu::TextureFormat::Rgba8Unorm,
            usage: wgpu::TextureUsages::RENDER_ATTACHMENT,
            view_formats: &[],
        });
        let view = texture.create_view(&Default::default());
        // A clear-only pass separates attachment/submission overhead from draw cost.
        for index in 0..=frames {
            let draw = index != 0;
            let started = Instant::now();
            let mut encoder = device.create_command_encoder(&Default::default());
            {
                let mut pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
                    label: Some("independent radial pass"),
                    color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                        view: &view,
                        depth_slice: None,
                        resolve_target: None,
                        ops: wgpu::Operations {
                            load: wgpu::LoadOp::Clear(wgpu::Color::WHITE),
                            store: wgpu::StoreOp::Store,
                        },
                    })],
                    timestamp_writes: timestamp.as_ref().map(|q| wgpu::RenderPassTimestampWrites {
                        query_set: q,
                        beginning_of_pass_write_index: Some(0),
                        end_of_pass_write_index: Some(1),
                    }),
                    ..Default::default()
                });
                if let Some(q) = &statistics {
                    pass.begin_pipeline_statistics_query(q, 0);
                }
                if draw {
                    frame.draw(&mut pass);
                }
                if statistics.is_some() {
                    pass.end_pipeline_statistics_query();
                }
            }
            if let Some(q) = &timestamp {
                encoder.resolve_query_set(q, 0..2, &resolve, 0);
            }
            if let Some(q) = &statistics {
                encoder.resolve_query_set(q, 0..1, &resolve, 256);
            }
            if timestamp.is_some() || statistics.is_some() {
                encoder.copy_buffer_to_buffer(&resolve, 0, &readback, 0, 512);
            }
            let commands = encoder.finish();
            let encode_ms = started.elapsed().as_secs_f64() * 1000.;
            let submit_start = Instant::now();
            queue.submit([commands]);
            let submit_cpu_ms = submit_start.elapsed().as_secs_f64() * 1000.;
            wait(&device)?;
            let submit_to_complete_ms = submit_start.elapsed().as_secs_f64() * 1000.;
            let (mut pass_ms, mut invocations) = (None, None);
            if timestamp.is_some() || statistics.is_some() {
                let (tx, rx) = std::sync::mpsc::channel();
                readback.slice(..).map_async(wgpu::MapMode::Read, move |r| {
                    let _ = tx.send(r);
                });
                wait(&device)?;
                rx.recv()??;
                let bytes = readback.slice(..).get_mapped_range()?;
                let value =
                    |offset| u64::from_le_bytes(bytes[offset..offset + 8].try_into().unwrap());
                if timestamp.is_some() {
                    pass_ms = Some(
                        (value(8).wrapping_sub(value(0))) as f64
                            * f64::from(queue.get_timestamp_period())
                            / 1_000_000.,
                    );
                }
                if statistics.is_some() {
                    invocations = Some(value(256));
                }
                drop(bytes);
                readback.unmap();
            }
            let pixels = u64::from(width) * u64::from(height);
            let hit_calls = if draw { pixels * 4 * count as u64 } else { 0 };
            emit(
                &mut file,
                &json!({"type":"frame","case":case,"phase":if !draw {"clear"} else if index==1 {"cold"} else {"warm"},
                "frame":index,"width":width,"height":height,"slices":count,"prepare_ms":prepare_ms,
                "encode_cpu_ms":encode_ms,"submit_cpu_ms":submit_cpu_ms,"submit_to_complete_ms":submit_to_complete_ms,
                "pass_timestamp_ms":pass_ms,"fragment_invocations":invocations,
                "logical_pixels":if draw {pixels} else {0},"aa_samples_per_pixel":4,
                "logical_scene_samples":if draw {pixels*4} else {0},"logical_sector_hit_calls":hit_calls,
                "logical_sector_hit_calls_per_second":hit_calls as f64/(submit_to_complete_ms/1000.)}),
            )?;
        }
        renderer.end_frame();
    }
    Ok(())
}

fn emit(file: &mut File, row: &Value) -> Result<()> {
    let line = serde_json::to_string(row)?;
    println!("{line}");
    writeln!(file, "{line}")?;
    file.flush()?;
    Ok(())
}
