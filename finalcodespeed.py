import os
import time
import requests
import pandas as pd
import asyncio
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, urljoin
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager
import json
import aiohttp

# Function to extract links asynchronously from a webpage
async def extract_links_async(session, url):
    try:
        async with session.get(url) as response:
            if response.status == 200:
                content = await response.text()
                soup = BeautifulSoup(content, "html.parser")
                links = soup.find_all('a', href=True)
                return [link['href'] for link in links if link['href'].startswith('http')]
            else:
                print(f"Failed to retrieve {url}: Status code {response.status}")
                return []
    except Exception as e:
        print(f"Error occurred while fetching {url}: {e}")
        return []

# Asynchronous function to crawl a website and collect all the URLs
async def crawl_website_async(start_url, domain):
    all_urls = set()
    to_crawl = [start_url]
    async with aiohttp.ClientSession() as session:
        while to_crawl:
            url = to_crawl.pop(0)
            if url in all_urls:
                continue

            print(f"Crawling {url}...")
            links = await extract_links_async(session, url)
            all_urls.add(url)

            for link in links:
                full_url = urljoin(url, link)
                if domain in urlparse(full_url).netloc and full_url not in all_urls:
                    to_crawl.append(full_url)

            await asyncio.sleep(0.5)  # Adjust as needed for server load

    return all_urls

# Function to create a Selenium WebDriver
def create_driver():
    chrome_options = ChromeOptions()
    chrome_options.add_argument("--headless")  # Optional: run in headless mode
    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chrome_options)
    return driver

# Function to run Lighthouse using Selenium
def run_lighthouse(url):
    driver = create_driver()
    driver.get(url)

    # Run Lighthouse CLI command and generate the report
    report_file = f'lighthouse_report_{urlparse(url).netloc}.json'
    os.system(f'lighthouse {url} --output json --quiet --chrome-flags="--headless" --output-path={report_file}')

    # Read the generated Lighthouse report
    with open(report_file, 'r') as f:
        data = json.load(f)

    # Clean up
    driver.quit()
    os.remove(report_file)

    return extract_metrics(data, url)

# Function to extract relevant metrics from Lighthouse results
def extract_metrics(data, url):
    try:
        lighthouse_data = data.get('categories', {})
        performance_score = lighthouse_data.get('performance', {}).get('score', 0) * 100
        seo_score = lighthouse_data.get('seo', {}).get('score', None)
        if seo_score is not None:
            seo_score *= 100
        pwa_score = lighthouse_data.get('pwa', {}).get('score', None)
        if pwa_score is not None:
            pwa_score *= 100

        audits = data.get('audits', {})
        load_time = audits.get('largest-contentful-paint', {}).get('numericValue', 0) / 1000
        fcp = audits.get('first-contentful-paint', {}).get('numericValue', 0) / 1000
        cls = audits.get('cumulative-layout-shift', {}).get('numericValue', 0)

        return {
            'URL': url,
            'Performance Score': performance_score,
            'SEO Score': seo_score,
            'PWA Score': pwa_score,
            'Load Time (seconds)': load_time,
            'First Contentful Paint (seconds)': fcp,
            'Cumulative Layout Shift (CLS)': cls,
            'Status': 'Success'
        }
    except KeyError as e:
        print(f"Error extracting metrics for {url}: {e}")
        return {'URL': url, 'Status': 'Failed'}

# Function to check if a URL redirects to a 404 page
def check_404(url):
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 404:
            return url, "Redirects to 404"
        return url, "Pass"
    except requests.exceptions.RequestException as e:
        print(f"Error occurred while checking {url}: {e}")
        return url, "Error checking URL"

# Optimized URL checking in Excel
def check_urls_in_excel(input_excel_file, output_excel_file, max_workers=10):
    df = pd.read_excel(input_excel_file)

    if 'URL' not in df.columns:
        print("The Excel file does not contain a column named 'URL'.")
        return
    urls = df['URL'].dropna().tolist()
    result = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(check_404, url) for url in urls]
        for future in as_completed(futures):
            url, status = future.result()
            result.append((url, status))

    df['Status'] = df['URL'].apply(lambda x: dict(result).get(x, "Empty URL"))
    df.to_excel(output_excel_file, index=False)
    print(f"Results written to {output_excel_file}")

# Function to save results to an Excel file
def save_to_excel(urls, output_file):
    df = pd.DataFrame(list(urls), columns=["URL"])
    df.to_excel(output_file, index=False)
    print(f"Saved {len(urls)} URLs to {output_file}")

# Function to save Lighthouse results to Excel
def save_results_to_excel(results, filename):
    df = pd.DataFrame(results)
    df.to_excel(filename, index=False)
    print(f"Saved Lighthouse results to {filename}")

# Main function to process crawling, 404 check, and Lighthouse analysis
async def main():
    start_url = input("Enter the website URL: ")
    domain = urlparse(start_url).netloc

    # Step 1: Crawl the website to extract all URLs
    all_urls = await crawl_website_async(start_url, domain)
    print(f"Extracted {len(all_urls)} URLs from {start_url}.")

    # Step 2: Check each URL for 404 redirects
    output404_file = 'output404resurrection.xlsx'
    to_check = all_urls.copy()
    to_check_404 = []

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(check_404, url) for url in to_check]
        for future in as_completed(futures):
            url, status = future.result()
            if status == "Redirects to 404":
                to_check_404.append(url)

    if to_check_404:
        save_to_excel(to_check_404, output404_file)

    # Step 3: Fetch Lighthouse results for non-404 URLs
    output_lighthouse_file = 'output_lighthouse_results.xlsx'
    results = []

    for url in all_urls:
        if url not in to_check_404:
            result = run_lighthouse(url)
            results.append(result)

    save_results_to_excel(results, output_lighthouse_file)

# Run the main function
if __name__ == "__main__":
    asyncio.run(main())
