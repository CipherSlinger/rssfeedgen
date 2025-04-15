# RSSFeedGen

A powerful RSS feed generator that scrapes content from specified websites and converts it into standardized RSS feeds. This tool is especially useful for websites that don't provide their own RSS feeds but publish regularly updated content.

## Features

* Scrapes web content using Playwright (headless browser automation)
* Generates standard RSS/XML feeds from scraped content
* Handles multiple websites with different page structures
* Automatic scheduled updates at configurable intervals
* Robust error handling with retries and timeouts
* Timezone support for accurate publication dates

## Use Cases

This tool is currently configured to generate RSS feeds for:
* Guangdong Science and Technology Department announcements
* Guangzhou Science and Technology Bureau policy documents
* Guangzhou Huangpu District Science and Technology Bureau information platform

You can customize it to generate feeds for any website with structured content.

## Requirements

* Python 3.7+
* Playwright
* Other dependencies listed in `requirements.txt`

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/CipherSlinger/rssfeedgen.git
   cd rssfeedgen
   ```

2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Install Playwright browsers:
   ```bash
   playwright install
   ```

## Usage

### Basic Usage

Run the script directly:
```bash
python main.py
```

Or use the provided batch file (Windows):
```bash
main.bat
```

### Configuration

To configure new sites to scrape, modify the `sites` list in `main.py`:

```python
sites = [
    (RSS(url="https://example.com/news",
         output_file='example.xml'),
     Selector(container='div.news-item',
              link='a.news-link',
              title='h2.news-title',
              date='span.news-date'))
]
```

Each site configuration requires:
1. An `RSS` object with the target URL and output file
2. A `Selector` object with CSS selectors for content containers, links, titles, and dates

### Scheduling

The default configuration updates every 5 minutes. You can change this by modifying:

```python
RSS.start_schedule(sites, hours=0, minutes=5, seconds=0)
```

## Output

The script generates XML files in the RSS 2.0 format that can be consumed by any RSS reader or aggregator.

## Troubleshooting

Common issues:
* **Selector timeout errors**: Check if the website structure has changed and update selectors accordingly
* **Network errors**: Verify your internet connection and the target website's availability
* **Date parsing errors**: Ensure the date format on the website is supported by the `dateutil` parser


## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
