use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::{Command, ExitStatus, Stdio};

const VERSION: &str = env!("CARGO_PKG_VERSION");

fn find_python() -> Option<PathBuf> {
    let candidates: Vec<&str> = if cfg!(windows) {
        vec!["python", "python3", "py"]
    } else {
        vec!["python3", "python"]
    };

    for candidate in candidates {
        let check = Command::new(candidate)
            .args(["-c", "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)"])
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status();

        if let Ok(status) = check {
            if status.success() {
                return Some(PathBuf::from(candidate));
            }
        }
    }
    None
}

fn is_sfp_root(dir: &Path) -> bool {
    dir.join("catalog.json").exists() && dir.join("mcp").join("sfp_hive.py").exists()
}

fn resolve_sfp_root() -> Result<PathBuf, String> {
    // 1. Check current directory and parents
    if let Ok(cwd) = env::current_dir() {
        let mut curr = cwd.as_path();
        loop {
            if is_sfp_root(curr) {
                return Ok(curr.to_path_buf());
            }
            match curr.parent() {
                Some(p) => curr = p,
                None => break,
            }
        }
    }

    // 2. Check executable's directory and parents
    if let Ok(exe_path) = env::current_exe() {
        let mut curr = exe_path.as_path();
        while let Some(parent) = curr.parent() {
            if is_sfp_root(parent) {
                return Ok(parent.to_path_buf());
            }
            curr = parent;
        }
    }

    // 3. Check SFP_ROOT / SFP_DIR environment variable
    for var_name in ["SFP_ROOT", "SFP_DIR"] {
        if let Ok(sfp_dir) = env::var(var_name) {
            let path = PathBuf::from(sfp_dir);
            if is_sfp_root(&path) {
                return Ok(path);
            }
        }
    }

    // 4. Default user folder ~/.sfp/root pointer or ~/.sfp/SFP
    let home = env::var_os("HOME")
        .or_else(|| env::var_os("USERPROFILE"))
        .map(PathBuf::from)
        .ok_or_else(|| "Could not determine user home directory.".to_string())?;

    let pointer_file = home.join(".sfp").join("root");
    if let Ok(content) = fs::read_to_string(&pointer_file) {
        let pointed = PathBuf::from(content.trim());
        if is_sfp_root(&pointed) {
            return Ok(pointed);
        }
    }

    let default_dir = home.join(".sfp").join("SFP");
    if is_sfp_root(&default_dir) {
        return Ok(default_dir);
    }

    // Clone into default_dir if missing
    eprintln!("\x1b[36mSetting up SFP in {}...\x1b[0m", default_dir.display());
    if let Some(parent) = default_dir.parent() {
        fs::create_dir_all(parent).map_err(|e| format!("Failed to create directory: {}", e))?;
    }

    let clone_status = Command::new("git")
        .args([
            "clone",
            "--depth",
            "1",
            "https://github.com/siddu1004/SFP.git",
            &default_dir.to_string_lossy(),
        ])
        .status()
        .map_err(|e| format!("Failed to run git: {}. Please ensure git is installed.", e))?;

    if !clone_status.success() {
        return Err("Failed to clone SFP repository.".to_string());
    }

    Ok(default_dir)
}

fn print_help() {
    println!(
        "\x1b[1m\x1b[36mSFP (Skills for Productivity)\x1b[0m v{} — 819 skills, one intelligent hive.
Give your AI coding agent the right skills for the job, not all of them.

\x1b[1mUSAGE:\x1b[0m
  \x1b[32msfp\x1b[0m <command> [options]
  \x1b[32msfp-hive\x1b[0m <command> [options]

\x1b[1mCOMMANDS:\x1b[0m
  \x1b[33minstall\x1b[0m [options]     Install skills into detected IDEs (Antigravity, Claude, Cursor, VS Code, etc.)
  \x1b[33mmcp\x1b[0m [options]         Run the SFP MCP server on stdio (or register with --tools <ide>)
  \x1b[33mrules\x1b[0m [options]       Add standing instructions to use SFP skills on substantial tasks
  \x1b[33mselect\x1b[0m \"<task>\"      Ask the hive which skills to load for a task
  \x1b[33mneeds\x1b[0m \"<task>\"       Check what capabilities or external tools a task needs
  \x1b[33mdoctor\x1b[0m              Check catalog, index, local models, and hive connections
  \x1b[33mroute\x1b[0m [args]          Manage or start the local model router (Ollama, LM Studio, etc.)
  \x1b[33mapps\x1b[0m [args]           Manage companion apps (OmniRoute, Strix, etc.)
  \x1b[33mlist\x1b[0m                List categories and install profiles
  \x1b[33mversion\x1b[0m             Show version information
  \x1b[33mhelp\x1b[0m                Show this help message

\x1b[1mEXAMPLES:\x1b[0m
  $ \x1b[32msfp install\x1b[0m                      # Install starter set into every IDE found
  $ \x1b[32msfp install --profile backend-dev\x1b[0m # Install backend-focused skills
  $ \x1b[32msfp mcp --tools antigravity,cursor\x1b[0m # Register MCP server in IDEs
  $ \x1b[32msfp select \"write unit tests\"\x1b[0m     # See which skills the hive recommends
  $ \x1b[32msfp doctor\x1b[0m                        # Verify health of catalog, index, and models

\x1b[1mUSE IN MCP CLIENTS (mcp.json):\x1b[0m
  {{
    \"mcpServers\": {{
      \"sfp\": {{
        \"command\": \"sfp\",
        \"args\": [\"mcp\"]
      }}
    }}
  }}

Docs & Source: \x1b[4mhttps://github.com/siddu1004/SFP\x1b[0m",
        VERSION
    );
}

fn main() {
    let args: Vec<String> = env::args().skip(1).collect();
    let command = args.first().map(|s| s.as_str());

    match command {
        None | Some("help") | Some("--help") | Some("-h") => {
            print_help();
            return;
        }
        Some("version") | Some("--version") | Some("-v") => {
            println!("sfp {}", VERSION);
            return;
        }
        _ => {}
    }

    let py_bin = match find_python() {
        Some(bin) => bin,
        None => {
            eprintln!("\x1b[31mError: Python 3.8+ is required to run SFP.\x1b[0m");
            eprintln!("Please install Python 3 from https://www.python.org/downloads/ and ensure it is on your PATH.");
            std::process::exit(1);
        }
    };

    let root_dir = match resolve_sfp_root() {
        Ok(dir) => dir,
        Err(err) => {
            eprintln!("\x1b[31mError:\x1b[0m {}", err);
            std::process::exit(1);
        }
    };

    let command_str = command.unwrap();
    let (target_script, target_args): (PathBuf, Vec<&str>) = match command_str {
        "mcp" => {
            let is_installer = args.iter().skip(1).any(|a| {
                a == "--tools"
                    || a == "--project"
                    || a == "--remove"
                    || a.starts_with("--tools=")
                    || a.starts_with("--project=")
            });
            if is_installer {
                let mut sub = vec!["mcp"];
                sub.extend(args.iter().skip(1).map(|s| s.as_str()));
                (root_dir.join("scripts").join("install.py"), sub)
            } else {
                (
                    root_dir.join("mcp").join("sfp_mcp.py"),
                    args.iter().skip(1).map(|s| s.as_str()).collect(),
                )
            }
        }
        "select" | "live" | "track" | "feedback" | "clusters" | "library" | "bundles" => (
            root_dir.join("mcp").join("sfp_hive.py"),
            args.iter().map(|s| s.as_str()).collect(),
        ),
        "needs" => {
            let mut sub = vec!["needs"];
            sub.extend(args.iter().skip(1).map(|s| s.as_str()));
            (root_dir.join("mcp").join("sfp_hive.py"), sub)
        }
        "doctor" => {
            let mut sub = vec!["doctor"];
            sub.extend(args.iter().skip(1).map(|s| s.as_str()));
            (root_dir.join("mcp").join("sfp_hive.py"), sub)
        }
        "route" => (
            root_dir.join("mcp").join("sfp_route.py"),
            args.iter().skip(1).map(|s| s.as_str()).collect(),
        ),
        "install" | "list" | "uninstall" | "rules" | "apps" => {
            let mut sub = vec![command_str];
            sub.extend(args.iter().skip(1).map(|s| s.as_str()));
            (root_dir.join("scripts").join("install.py"), sub)
        }
        flag if flag.starts_with('-') => {
            let mut sub = vec!["install"];
            sub.extend(args.iter().map(|s| s.as_str()));
            (root_dir.join("scripts").join("install.py"), sub)
        }
        other => {
            eprintln!("\x1b[31mUnknown command:\x1b[0m {}\n", other);
            print_help();
            std::process::exit(1);
        }
    };

    let mcp_dir = root_dir.join("mcp");
    let existing_pythonpath = env::var("PYTHONPATH").unwrap_or_default();
    let new_pythonpath = if existing_pythonpath.is_empty() {
        mcp_dir.to_string_lossy().to_string()
    } else {
        let sep = if cfg!(windows) { ";" } else { ":" };
        format!("{}{}{}", mcp_dir.to_string_lossy(), sep, existing_pythonpath)
    };

    let status: Result<ExitStatus, std::io::Error> = Command::new(&py_bin)
        .arg(&target_script)
        .args(&target_args)
        .current_dir(&root_dir)
        .env("PYTHONPATH", new_pythonpath)
        .env("PYTHONIOENCODING", "utf-8")
        .env("PYTHONUTF8", "1")
        .stdin(Stdio::inherit())
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit())
        .status();

    match status {
        Ok(exit_code) => {
            if let Some(code) = exit_code.code() {
                std::process::exit(code);
            }
        }
        Err(e) => {
            eprintln!("\x1b[31mFailed to execute process:\x1b[0m {}", e);
            std::process::exit(1);
        }
    }
}
