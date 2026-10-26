//! Review-only image input and previews; never part of chart Settings.
use base64::{Engine, engine::general_purpose::STANDARD};
use image::{ImageDecoder, ImageFormat, ImageReader};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::{collections::HashMap, io::Cursor, path::Path};

const MAX_BYTES: usize = 20 * 1024 * 1024;
fn png(data: &[u8]) -> Result<(Vec<u8>, u32, u32), String> {
    if data.len() > MAX_BYTES {
        return Err("Review images must be at most 20 MiB".into());
    }
    let mut reader = ImageReader::new(Cursor::new(data))
        .with_guessed_format()
        .map_err(|e| e.to_string())?;
    if !matches!(
        reader.format(),
        Some(ImageFormat::Png | ImageFormat::Jpeg | ImageFormat::WebP)
    ) {
        return Err("Choose a PNG, JPEG or WebP image".into());
    }
    let mut limits = image::Limits::default();
    limits.max_image_width = Some(8192);
    limits.max_image_height = Some(8192);
    limits.max_alloc = Some(128 * 1024 * 1024);
    reader.limits(limits);
    let mut decoder = reader
        .into_decoder()
        .map_err(|e| format!("Could not decode image: {e}"))?;
    if decoder.total_bytes() > 128 * 1024 * 1024 {
        return Err("Decoded review image exceeds 128 MiB; use a smaller image".into());
    }
    let orientation = decoder
        .orientation()
        .map_err(|e| format!("Could not read image orientation: {e}"))?;
    let mut image = image::DynamicImage::from_decoder(decoder)
        .map_err(|e| format!("Could not decode image: {e}"))?;
    image.apply_orientation(orientation);
    let (width, height) = (image.width(), image.height());
    let mut output = Cursor::new(Vec::new());
    image
        .write_to(&mut output, ImageFormat::Png)
        .map_err(|e| e.to_string())?;
    let bytes = output.into_inner();
    if bytes.len() > MAX_BYTES {
        return Err("Decoded review image exceeds 20 MiB; use a smaller image".into());
    }
    Ok((bytes, width, height))
}
pub(crate) fn attachment(data: &[u8], name: &str) -> Result<Value, String> {
    let (bytes, width, height) = png(data)?;
    let sha = format!("{:x}", Sha256::digest(&bytes));
    Ok(
        json!({"id":sha,"name":name,"mime_type":"image/png","bytes":bytes.len(),"width":width,"height":height,"data":STANDARD.encode(bytes)}),
    )
}
#[pyo3::pyfunction]
pub(crate) fn review_image_json(data: &[u8], name: &str) -> pyo3::PyResult<String> {
    attachment(data, name)
        .map(|v| v.to_string())
        .map_err(crate::invalid)
}
pub(crate) fn clipboard() -> Result<Value, String> {
    let mut clipboard = arboard::Clipboard::new().map_err(|e| e.to_string())?;
    let image = clipboard
        .get_image()
        .map_err(|_| "Clipboard does not contain an image".to_owned())?;
    if image.width > 8192 || image.height > 8192 || image.bytes.len() > 128 * 1024 * 1024 {
        return Err("Clipboard image is too large; use an image up to 8192 pixels per side".into());
    }
    let rgba = image::RgbaImage::from_raw(
        image.width as u32,
        image.height as u32,
        image.bytes.into_owned(),
    )
    .ok_or("Invalid clipboard image")?;
    let mut bytes = Cursor::new(Vec::new());
    image::DynamicImage::ImageRgba8(rgba)
        .write_to(&mut bytes, ImageFormat::Png)
        .map_err(|e| e.to_string())?;
    attachment(bytes.get_ref(), "Clipboard image.png")
}
fn bytes(item: &Value, cache: &str) -> Result<Vec<u8>, String> {
    if let Some(data) = item["data"].as_str() {
        STANDARD.decode(data).map_err(|e| e.to_string())
    } else {
        let file = item["file"].as_str().ok_or("Missing image reference")?;
        let sha = item["sha256"].as_str().ok_or("Missing image digest")?;
        if sha.len() != 64
            || !sha.chars().all(|c| c.is_ascii_hexdigit())
            || file != format!("attachments/{sha}.png")
        {
            return Err("Invalid review image reference".into());
        }
        std::fs::read(Path::new(cache).join(file)).map_err(|e| e.to_string())
    }
}
pub(crate) fn append(items: &mut Vec<Value>, item: Value) {
    if !items.iter().any(|v| v["id"] == item["id"]) {
        items.push(item);
    }
}
#[derive(Default)]
pub(crate) struct ImageUi {
    textures: HashMap<String, egui::TextureHandle>,
    preview: Option<Value>,
    pub error: String,
}
impl ImageUi {
    pub fn retain(&mut self, ids: &std::collections::HashSet<String>) {
        let preview = self
            .preview
            .as_ref()
            .and_then(|v| v["id"].as_str())
            .map(str::to_owned);
        self.textures
            .retain(|id, _| ids.contains(id) || preview.as_ref() == Some(id));
    }
    pub fn dismiss_preview(&mut self) -> bool {
        self.preview.take().is_some()
    }
    fn texture(
        &mut self,
        ctx: &egui::Context,
        item: &Value,
        cache: &str,
    ) -> Result<egui::TextureHandle, String> {
        let id = item["id"].as_str().ok_or("Missing image ID")?;
        if let Some(texture) = self.textures.get(id) {
            return Ok(texture.clone());
        }
        let data = bytes(item, cache)?;
        let image = image::load_from_memory_with_format(&data, ImageFormat::Png)
            .map_err(|e| e.to_string())?
            .to_rgba8();
        let color = egui::ColorImage::from_rgba_unmultiplied(
            [image.width() as usize, image.height() as usize],
            image.as_raw(),
        );
        let texture = ctx.load_texture(
            format!("review-image-{id}"),
            color,
            egui::TextureOptions::LINEAR,
        );
        self.textures.insert(id.into(), texture.clone());
        Ok(texture)
    }
    pub fn editor(
        &mut self,
        ui: &mut egui::Ui,
        items: &mut Vec<Value>,
        cache: &str,
        prefix: &str,
        controls: &mut HashMap<String, egui::Rect>,
    ) {
        ui.horizontal(|ui| {
            let attach = ui.button("Attach image…");
            controls.insert(format!("{prefix}_attach"), attach.rect);
            if attach.clicked() {
                if let Some(files) = rfd::FileDialog::new()
                    .add_filter("Images", &["png", "jpg", "jpeg", "webp"])
                    .pick_files()
                {
                    for path in files {
                        let result = std::fs::metadata(&path)
                            .map_err(|e| e.to_string())
                            .and_then(|m| {
                                if m.len() > MAX_BYTES as u64 {
                                    Err("Review images must be at most 20 MiB".into())
                                } else {
                                    std::fs::read(&path).map_err(|e| e.to_string())
                                }
                            })
                            .and_then(|data| {
                                attachment(
                                    &data,
                                    &path.file_name().unwrap_or_default().to_string_lossy(),
                                )
                            });
                        match result {
                            Ok(item) => {
                                append(items, item);
                                self.error.clear();
                            }
                            Err(e) => self.error = e,
                        }
                    }
                }
            }
            let paste = ui.button("Paste image");
            controls.insert(format!("{prefix}_paste"), paste.rect);
            if paste.clicked() {
                match clipboard() {
                    Ok(item) => {
                        append(items, item);
                        self.error.clear();
                    }
                    Err(e) => self.error = e,
                }
            }
            if items.is_empty() {
                ui.weak("PNG · JPEG · WebP · Ctrl/Cmd+V in comments");
            }
        });
        if !items.is_empty() {
            let mut remove = None;
            egui::ScrollArea::horizontal()
                .id_salt(format!("{prefix}-images"))
                .max_height(80.)
                .show(ui, |ui| {
                    ui.horizontal(|ui| {
                        for (index, item) in items.iter().enumerate() {
                            ui.group(|ui| {
                                ui.horizontal(|ui| {
                                    match self.texture(ui.ctx(), item, cache) {
                                        Ok(texture) => {
                                            let response = ui.add(
                                                egui::Image::new(&texture)
                                                    .max_size(egui::vec2(72., 52.))
                                                    .sense(egui::Sense::click()),
                                            );
                                            controls.insert(
                                                format!(
                                                    "{prefix}_image:{}",
                                                    item["id"].as_str().unwrap_or("")
                                                ),
                                                response.rect,
                                            );
                                            if response.clicked() {
                                                self.preview = Some(item.clone());
                                            }
                                        }
                                        Err(e) => {
                                            ui.label("Image unavailable");
                                            self.error = e;
                                        }
                                    }
                                    let button =
                                        ui.small_button("×").on_hover_text("Remove attachment");
                                    controls.insert(
                                        format!(
                                            "{prefix}_image_remove:{}",
                                            item["id"].as_str().unwrap_or("")
                                        ),
                                        button.rect,
                                    );
                                    if button.clicked() {
                                        remove = Some(index);
                                    }
                                });
                            });
                        }
                    });
                });
            if let Some(index) = remove {
                items.remove(index);
            }
        }
        if !self.error.is_empty() {
            ui.colored_label(egui::Color32::from_rgb(170, 45, 45), &self.error);
        }
    }
    pub fn preview(&mut self, ctx: &egui::Context, cache: &str) {
        let Some(item) = self.preview.clone() else {
            return;
        };
        let mut open = true;
        egui::Window::new(item["name"].as_str().unwrap_or("Review image"))
            .id(egui::Id::new("review_image_preview"))
            .open(&mut open)
            .show(ctx, |ui| {
                if let Ok(texture) = self.texture(ctx, &item, cache) {
                    ui.add(egui::Image::new(&texture).max_size(egui::vec2(700., 500.)));
                }
            });
        if !open {
            self.preview = None;
        }
    }
}
