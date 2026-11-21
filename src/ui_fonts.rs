//! Editor text uses egui's font stack, independently of chart text rasterization.
use std::sync::OnceLock;

pub(crate) fn install(ctx: &egui::Context) {
    static FONTS: OnceLock<egui::FontDefinitions> = OnceLock::new();
    let fonts = FONTS.get_or_init(|| {
        let mut fonts = egui::FontDefinitions::default();
        let mut db = fontdb::Database::new();
        db.load_system_fonts();
        let mut seen = std::collections::HashSet::new();
        // Keep the normal UI face; these are per-glyph fallbacks for scientific
        // notation and user text, including U+207B absent from egui's default.
        for family in [
            "DejaVu Sans",
            "Segoe UI",
            "Segoe UI Symbol",
            "Noto Sans",
            "Noto Sans Symbols 2",
            "Apple Symbols",
            "Arial Unicode MS",
        ] {
            let Some(id) = db.query(&fontdb::Query {
                families: &[fontdb::Family::Name(family)],
                ..Default::default()
            }) else {
                continue;
            };
            if !seen.insert(id) {
                continue;
            }
            let Some(data) = db.with_face_data(id, |bytes, index| {
                let mut data = egui::FontData::from_owned(bytes.to_vec());
                data.index = index;
                data
            }) else {
                continue;
            };
            let name = format!("editor-fallback-{family}");
            fonts
                .font_data
                .insert(name.clone(), std::sync::Arc::new(data));
            for family in [egui::FontFamily::Proportional, egui::FontFamily::Monospace] {
                fonts.families.entry(family).or_default().push(name.clone());
            }
        }
        fonts
    });
    ctx.set_fonts(fonts.clone());
}

pub(crate) fn resolve(family: &str) -> Result<(Vec<u8>, u32), String> {
    let mut db = fontdb::Database::new();
    db.load_system_fonts();
    let id = db
        .query(&fontdb::Query {
            families: &[fontdb::Family::Name(family)],
            ..Default::default()
        })
        .ok_or_else(|| format!("Review font {family:?} is not installed"))?;
    db.with_face_data(id, |data, index| (data.to_vec(), index))
        .ok_or_else(|| "Review font data is unavailable".into())
}

pub(crate) fn install_review(ctx: &egui::Context, family: &str) -> Result<(), String> {
    let (bytes, index) = resolve(family)?;
    let mut fonts = egui::FontDefinitions::default();
    let mut data = egui::FontData::from_owned(bytes);
    data.index = index;
    fonts
        .font_data
        .insert("figgy-review".into(), std::sync::Arc::new(data));
    for names in fonts.families.values_mut() {
        names.push("figgy-review".into());
    }
    let mut names = vec!["figgy-review".into()];
    names.extend(
        fonts.families[&egui::FontFamily::Proportional]
            .iter()
            .filter(|n| *n != "figgy-review")
            .cloned(),
    );
    fonts
        .families
        .insert(egui::FontFamily::Name("figgy-review".into()), names);
    ctx.set_fonts(fonts);
    Ok(())
}
