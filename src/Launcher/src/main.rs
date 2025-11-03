use colored::*;
use std::fs;
use std::io::{self, Write};
use std::path::PathBuf;
use std::process::{Command, exit};

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

fn get_app_version() -> String {
    match fs::read_to_string("version.txt") {
        Ok(app_version) => {
            return format!("Version: {}\n", app_version.trim().bright_magenta());
        }
        Err(_) => {
            return format!("{}\n", "Version: [NOT FOUND]".dimmed());
        }
    }
}

fn pause_on_error(message: &str, exit_code: i32) {
    println!("\n{}", message);
    print!("Press Enter to exit...");
    // We need to flush stdout to ensure the message appears before the program waits for input.
    io::stdout().flush().unwrap();
    let _ = io::stdin().read_line(&mut String::new());
    exit(exit_code); // Exit the process with a non-zero exit code to indicate failure.
}

fn make_a_link(url: &str, text: Option<&str>) -> String {
    let display_text = text.unwrap_or(url);
    return format!("\x1B]8;;{}\x07{}\x1B]8;;\x07", url, display_text);
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
    println!("{}", get_app_version());

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
                let error_msg = format!(
                    "Incompatible Python version. Required: {}, Found: {}\nPlease check the installation instruction on the README.md or on {}",
                    MIN_PYTHON_VERSION.green(),
                    installed_version_str.red(),
                    make_a_link(&"https://github.com/DigitalHolography/DopplerManager", None).bright_blue()
                );

                pause_on_error(&error_msg, 1);
                return Ok(());
            }
        }
        Err(e) => {
            pause_on_error(&e.red(), 1);
            return Ok(()); // Will not be reached due to exit in pause_on_error
        }
    }

    println!();

    // ================= ENV =================

    println!("{}", "Creating virtual environment...".yellow());

    let venv_status_result = Command::new(&python_executable)
        .args(&["-m", "venv", "venv"])
        .status();

    match venv_status_result {
        Ok(status) => {
            if !status.success() {
                pause_on_error(&"Failed to create virtual environment.".red(), 1);
            }
        }
        Err(e) => {
            let error_msg = format!("Error executing python to create virtual environment: {}", e);
            pause_on_error(&error_msg.red(), 1);
        }
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

    let pip_status_result = Command::new(&pip_path)
        .args(&["install", "-r", "requirements.txt"])
        .status();

    match pip_status_result {
        Ok(status) => {
            if !status.success() {
                pause_on_error(&"Failed to install dependencies.".red(), 1);
            }
        }
        Err(e) => {
            let error_msg = format!("Failed to run pip. Is 'requirements.txt' present?\nError: {}", e);
            pause_on_error(&error_msg.red(), 1);
        }
    }

    println!("{}", "Dependencies installed successfully.\n".green());

    // ================= APP =================

    println!(
        "{}",
        "Running the Streamlit application... (Press Ctrl+C to stop)".yellow()
    );

    let streamlit_status_result = Command::new(&streamlit_path)
        .arg("run")
        .arg("app.py")
        .status();
    
    match streamlit_status_result {
        Ok(status) => {
            if !status.success() {
                pause_on_error(&"Streamlit application exited with an error.".red(), 1);
            }
        }

        Err(e) => {
            let error_msg = format!("Failed to run streamlit. Is 'app.py' present?\nError: {}", e);
            pause_on_error(&error_msg.red(), 1);
        }
    }

    Ok(())
}
