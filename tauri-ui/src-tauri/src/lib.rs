// Prevents additional console window on Windows in release.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::env;
use std::path::PathBuf;
use std::process::Command;

fn project_root() -> PathBuf {
    if let Ok(env_root) = env::var("AUTO_CHORDS_ROOT") {
        return PathBuf::from(env_root);
    }
    let cwd = env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    if cwd.parent().map(|p| p.join("wav_a_wavs.py").exists()).unwrap_or(false) {
        return cwd.parent().unwrap().to_path_buf();
    }
    cwd.ancestors().nth(2).unwrap_or(&cwd).to_path_buf()
}

#[tauri::command]
fn detect_chords(wav_path: String, bpm: f64, bpb: u64) -> Result<String, String> {
    let root = project_root();
    let script = root.join("wav_a_wavs.py");

    if !script.exists() {
        return Err(format!(
            "No trobo el script: {}. Defineix AUTO_CHORDS_ROOT o executa des del directori correcte.",
            script.display()
        ));
    }

    let bpm_arg = bpm.to_string();
    let bpb_arg = bpb.to_string();

    let output = Command::new("python3")
        .arg(&script)
        .arg(&wav_path)
        .arg(&bpm_arg)
        .arg(&bpb_arg)
        .output()
        .map_err(|e| format!("Error executant python3: {}", e))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("Python ha fallat (codi {:?}):\\n{}", output.status.code(), stderr));
    }

    Ok(String::from_utf8_lossy(&output.stdout).to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    // Workaround per a WebKitGTK 2.44 + gràfiques antigues (GMA 3100) o
    // NVIDIA Kepler (GT 730) en Linux: el renderitzat accelerat per
    // DMA-BUF/EGL pot deixar la finestra en blanc. Les dues variables
    // següents forcen compositing per software (CPU).
    // Vegeu INSTALL.md per detalls.
    #[cfg(target_os = "linux")]
    {
        std::env::set_var("WEBKIT_DISABLE_DMABUF_RENDERER", "1");
        std::env::set_var("WEBKIT_DISABLE_COMPOSITING_MODE", "1");
    }

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![detect_chords])
        .run(tauri::generate_context!())
        .expect("Error iniciant l'aplicació Tauri");
}
