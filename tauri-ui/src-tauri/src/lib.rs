// Prevents additional console window on Windows in release.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::env;
use std::path::PathBuf;
use std::process::Command;

/// Troba el directori arrel del projecte (el que conté `wav_a_wavs.py`,
/// `tauri-ui/`, `sonic-annotator`, etc.).
///
/// Ordre de prioritat:
/// 1. Variable d'entorn `AUTO_CHORDS_ROOT` (recomanat per a l'AppImage).
/// 2. Cerca cap amunt des del cwd un directori amb `wav_a_wavs.py`.
/// 3. Fallback: puja 2 nivells (cas `tauri dev` des de `src-tauri/`).
fn project_root() -> PathBuf {
    if let Ok(env_root) = env::var("AUTO_CHORDS_ROOT") {
        if PathBuf::from(&env_root).is_dir() {
            return PathBuf::from(env_root);
        }
    }
    let cwd = env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    for anc in cwd.ancestors() {
        if anc.join("wav_a_wavs.py").is_file() {
            return anc.to_path_buf();
        }
    }
    cwd.ancestors().nth(2).unwrap_or(&cwd).to_path_buf()
}

/// Executa el pipeline d'anàlisi (Python) i retorna el JSON resultant.
///
/// El script `tauri-ui/python/analyze.py` és l'encarregat de córrer
/// `wav_a_wavs.py` i convertir les sortides (CSV) en un JSON estructurat
/// per al frontend.
#[tauri::command]
fn analyze(wav_path: String, bpm: f64, bpb: u64) -> Result<String, String> {
    let root = project_root();
    let script = root.join("tauri-ui").join("python").join("analyze.py");

    if !script.exists() {
        return Err(format!(
            "No trobo el script d'anàlisi: {}. Defineix AUTO_CHORDS_ROOT \
             o executa `tauri dev` des del projecte.",
            script.display()
        ));
    }

    let output = Command::new("python3")
        .arg(&script)
        .arg(&wav_path)
        .arg(bpm.to_string())
        .arg(bpb.to_string())
        .output()
        .map_err(|e| format!("Error executant python3: {}", e))?;

    // analyze.py sempre retorna JSON a stdout (resultat o {error}).
    // Si n'hi ha, el retornem tal qual i que decideixi el frontend.
    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    if !stdout.trim().is_empty() {
        return Ok(stdout);
    }

    let stderr = String::from_utf8_lossy(&output.stderr);
    Err(format!(
        "Python no ha retornat res (codi {:?}):\n{}",
        output.status.code(),
        stderr
    ))
}

/// Desa els canvis editats al disc (CSV + regeneració de clips WAV).
#[tauri::command]
fn save_changes(payload: String) -> Result<String, String> {
    let root = project_root();
    let script = root.join("tauri-ui").join("python").join("save.py");

    if !script.exists() {
        return Err(format!(
            "No trobo el script de desat: {}. Defineix AUTO_CHORDS_ROOT.",
            script.display()
        ));
    }

    let output = Command::new("python3")
        .arg(&script)
        .arg(&payload)
        .output()
        .map_err(|e| format!("Error executant python3: {}", e))?;

    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    if !stdout.trim().is_empty() {
        return Ok(stdout);
    }

    let stderr = String::from_utf8_lossy(&output.stderr);
    Err(format!(
        "Python no ha retornat res (codi {:?}):\n{}",
        output.status.code(),
        stderr
    ))
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
        .invoke_handler(tauri::generate_handler![analyze, save_changes])
        .run(tauri::generate_context!())
        .expect("Error iniciant l'aplicació Tauri");
}
