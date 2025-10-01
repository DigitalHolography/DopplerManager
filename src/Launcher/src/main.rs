use colored::*;
use std::io;
use std::path::PathBuf;
use std::process::Command;

const MIN_PYTHON_VERSION: &str = "3.13.0";

#[derive(Debug, PartialEq, PartialOrd)]
struct Version {
    major: u32,
    minor: u32,
    patch: u32,
}

impl Version {
    /// Parses a version string (e.g., "Python 3.10.4") into a Version struct.
    fn from_str(version_str: &str) -> Option<Self> {
        let version_part = version_str.split_whitespace().last()?;
        let parts: Vec<u32> = version_part
            .split('.')
            .filter_map(|s| s.parse().ok())
            .collect();

        if parts.len() >= 2 {
            let major = parts[0];
            let minor = parts[1];
            // Assume patch is 0 if not present
            let patch = if parts.len() >= 3 { parts[2] } else { 0 };
            Some(Version {
                major,
                minor,
                patch,
            })
        } else {
            None
        }
    }

    fn to_str(&self) -> String {
        format!("{}.{}.{}", self.major, self.minor, self.patch)
    }
}

/// Finds a suitable python executable and returns its name and version.
fn find_python() -> Result<(String, Version), String> {
    for cmd_name in ["python3", "python"].iter() {
        if let Ok(output) = Command::new(cmd_name).arg("--version").output() {
            if output.status.success() {
                let version_str = String::from_utf8_lossy(&output.stdout);
                if let Some(version) = Version::from_str(&version_str) {
                    // Found a working command, return it and the version
                    return Ok((cmd_name.to_string(), version));
                }
            }
        }
    }
    Err("Could not find a valid Python installation.".to_string())
}

fn main() -> io::Result<()> {
    // --- Display ASCII Art Banner ---
    let banner = r#"
 ██████████                               ████
░░███░░░░███                             ░░███
 ░███   ░░███  ██████  ████████  ████████ ░███   ██████  ████████
 ░███    ░███ ███░░███░░███░░███░░███░░███░███  ███░░███░░███░░███
 ░███    ░███░███ ░███ ░███ ░███ ░███ ░███░███ ░███████  ░███ ░░░
 ░███    ███ ░███ ░███ ░███ ░███ ░███ ░███░███ ░███░░░   ░███
 ██████████  ░░██████  ░███████  ░███████ █████░░██████  █████
░░░░░░░░░░    ░░░░░░   ░███░░░   ░███░░░ ░░░░░  ░░░░░░  ░░░░░
                        ░███      ░███
 ██████   ██████       █████     █████
░░██████ ██████       ░░░░░     ░░░░░
 ░███░█████░███   ██████  ████████    ██████    ███████  ██████  ████████
 ░███░░███ ░███  ░░░░░███░░███░░███  ░░░░░███  ███░░███ ███░░███░░███░░███
 ░███ ░░░  ░███   ███████ ░███ ░███   ███████ ░███ ░███░███████  ░███ ░░░
 ░███      ░███  ███░░███ ░███ ░███  ███░░███ ░███ ░███░███░░░   ░███
 █████     █████░░████████████ █████░░████████░░███████░░██████  █████
░░░░░     ░░░░░  ░░░░░░░░░░░░ ░░░░░  ░░░░░░░░  ░░░░░███ ░░░░░░  ░░░░░
                                                ███ ░███
                                               ░░██████
                                                ░░░░░░
    "#;
    println!("{}", banner.yellow());

    // ================= PYTHON CHECK =================

    let min_version = Version::from_str(MIN_PYTHON_VERSION).unwrap();
    let python_executable: String;

    match find_python() {
        Ok((executable, installed_version)) => {
            let installed_version_str = installed_version.to_str();

            println!(
                "Found Python {} using executable '{}'",
                installed_version_str, executable
            );

            if installed_version >= min_version {
                println!("{}", "Python version check passed.".green());
                python_executable = executable;
            } else {
                println!(
                    "{} Required version: {}, Found version: {}",
                    "Incompatible Python version.".red(),
                    MIN_PYTHON_VERSION.green(),
                    installed_version_str.red()
                );
                return Ok(());
            }
        }

        Err(e) => {
            println!("{}", e.red());
            return Ok(());
        }
    }

    println!();

    // ================= ENV =================

    println!("{}", "Creating virtual environment...".yellow());

    let venv_status = Command::new(&python_executable)
        .args(&["-m", "venv", "venv"])
        .status()?;

    if !venv_status.success() {
        println!("{}", "Failed to create virtual environment.".red());
        return Ok(());
    }

    println!("{}", "Virtual environment created successfully.\n".green());

    let venv_dir = PathBuf::from("venv");

    let (pip_path, streamlit_path) = {
        (
            venv_dir.join("Scripts").join("pip"),
            venv_dir.join("Scripts").join("streamlit"),
        )
    };

    println!(
        "{}",
        "Installing dependencies from requirements.txt...".yellow()
    );

    let pip_status = Command::new(pip_path)
        .args(&["install", "-r", "requirements.txt"])
        .status()?;

    if !pip_status.success() {
        println!("{}", "Failed to install dependencies.".red());
        return Ok(());
    }

    println!("{}", "Dependencies installed successfully.\n".green());

    // ================= APP =================

    println!(
        "{}",
        "Running the Streamlit application... (Press Ctrl+C to stop)".yellow()
    );

    let streamlit_status = Command::new(streamlit_path)
        .arg("run")
        .arg("app.py")
        .status()?;

    if !streamlit_status.success() {
        println!("{}", "Failed to run the Streamlit application.".red());
    }

    Ok(())
}
