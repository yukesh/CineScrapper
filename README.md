# 🎬 CineScrapper

CineScrapper is a Python command-line tool that scrapes Wikipedia for cinema data (such as Tamil-language film listings).  
It uses a local cache to avoid unnecessary repeated Wikipedia API calls and provides structured logging with color output.

---

## 🚀 Features

- Scrape film data from **Wikipedia** master pages.
- Filter by **year** (default: current year).
- Local **cache layer** (`site_cache/`) to reduce API calls.
- Configurable **logging level** with colored console output.
- Modular design for easy extension (parser, models, constants, helpers).

---

## 📦 Installation

Clone this repository and navigate into it:

```bash
git clone https://github.com/yukesh/CineScrapper.git
cd CineScrapper
```

### 1️⃣ Using a Virtual Environment (Recommended)

It’s best practice to run CineScrapper in a virtual environment to avoid conflicts with system packages.

```bash
# Create a virtual environment
python -m venv venv

# Activate the virtual environment
source venv/bin/activate   # macOS/Linux
# OR
venv\Scripts\activate      # Windows

# Upgrade pip inside the venv
pip install --upgrade pip

# Install CineScrapper in editable mode
pip install -e .

# Or install normally
pip install .

# Or Install using requirements.txt (optional)
pip install -r requirements.txt

# Clear the cache if needed
rm -rf site_cache/*

# Run the CLI
cinescrapper --help

# To deactivate the virtual environment when done
deactivate
```
### 2️⃣ Without a Virtual Environment
You can also install CineScrapper globally, but this is not recommended.
```bash
# Install globally for current user
python -m pip install --user -e /path/to/CineScrapper

# Or install normally
python -m pip install --user /path/to/CineScrapper

# Or Install using requirements.txt (optional)
python -m pip install --user /path/to/CineScrapper -r requirements.txt

# Add to ~/.zshrc for permanent access
export PATH="$HOME/.local/bin:$PATH"

# Clear the cache if needed
rm -rf site_cache/*

# Run the CLI:
cinescrapper --help
 
# To uninstall
pip uninstall cinescrapper
```

## ⚙️ Usage
Run the script with optional arguments:

```bash
python -m cinescrapper --year 2025 --log-level DEBUG
```
### Arguments

| Argument      | Type | Default      | Description                                          |
|---------------|------|--------------|------------------------------------------------------|
| `--year`      | int  | current year | Specify the year to scrape                           |
| `--log-level` | str  | INFO         | Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `--help`      |      |              | Show help message and exit                           |


### Example
#### This command scrapes film data for the year 2025 with detailed debug logging.
```bash
python -m cinescrapper --year 2025 --log-level INFO
```

## 🛠️ Project Structure

```
cinescrapper/
├── __init__.py         # Package initializer
├── __main__.py         # CLI entry point
├── cine_constants.py   # Constants (e.g., URLs, keys)
├── cine_helper.py      # Utility/helper functions
├── cine_model.py       # Data models (film, metadata, etc.)
├── cine_parser.py      # Parsing logic for Wikipedia pages
├── logger.py           # Logging setup with colors
├── scrapper.py         # Main scraping workflow
├── wiki_client.py      # Handles Wikipedia API interaction
├── requirements.txt    # List of dependencies for pip installation
└── site_cache/         # Cached wiki responses to reduce API calls
    └── ... (cached files)
```

## 🏁 Getting Started

1. Clone the repository.

2. Install dependencies (using virtualenv or globally).

3. Run the scraper:
```bash
cinescrapper --year 2025
```
4. Clear the cache if needed.
```bash
rm -rf site_cache/*
```




