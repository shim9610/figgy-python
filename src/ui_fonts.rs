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
