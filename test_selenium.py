import time
import requests
import pandas as pd
import asyncio
import aiohttp
import urllib.parse
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, urljoin

# Function to extract links from a webpage
def extract_links(url, retries=3):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'DNT': '1',
    }
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=10, verify=True)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, "html.parser")
                links = soup.find_all('a', href=True)
                url_list = [link['href'] for link in links if link['href'].startswith('http')]
                return url_list
            else:
                print(f"Failed to retrieve {url}: Status code {response.status_code}")
                return []
        except requests.exceptions.RequestException as e:
            print(f"Error occurred while fetching {url}: {e}")
            return []

# Asynchronous function to fetch PageSpeed Insights using Lighthouse with retry logic
async def fetch_pagespeed_insights_async(url, session, api_key, strategy, semaphore, retries=3):
    url_encoded = urllib.parse.quote(url, safe=":/")
    api_url = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={url_encoded}&key={api_key}&strategy={strategy}"

    async with semaphore:  # Limit the number of concurrent requests
        for attempt in range(retries):
            try:
                await asyncio.sleep(1)  # Added delay before the request
                async with session.get(api_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        metrics = extract_metrics(data, url, url_encoded, strategy)
                        return metrics
                    elif response.status == 500:
                        print(f"Error fetching data for {url}: Server error (500). Retrying...")
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    else:
                        print(f"Error fetching data for {url}: {response.status}.")
                        return {'URL': url, 'Status': 'Failed', 'Report Link': api_url}
            except Exception as e:
                print(f"Error occurred while fetching data for {url}: {e}. Retrying...")
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
        print(f"Failed to fetch data for {url} after {retries} attempts.")
        return {'URL': url, 'Status': 'Failed', 'Report Link': api_url}

# Function to extract relevant metrics from Lighthouse results
def extract_metrics(data, url, url_encoded, strategy):
    try:
        lighthouse_data = data.get('lighthouseResult', {})
        performance_score = lighthouse_data.get('categories', {}).get('performance', {}).get('score', 0) * 100
        seo_score = lighthouse_data.get('categories', {}).get('seo', {}).get('score', None)
        if seo_score is not None:
            seo_score *= 100

        pwa_score = lighthouse_data.get('categories', {}).get('pwa', {}).get('score', None)
        if pwa_score is not None:
            pwa_score *= 100

        core_web_vitals = lighthouse_data.get('audits', {})
        load_time = core_web_vitals.get('largest-contentful-paint', {}).get('numericValue', 0) / 1000
        fcp = core_web_vitals.get('first-contentful-paint', {}).get('numericValue', 0) / 1000
        lcp = core_web_vitals.get('largest-contentful-paint', {}).get('numericValue', 0) / 1000
        ttb = core_web_vitals.get('total-blocking-time', {}).get('numericValue', 0) / 1000
        speed_index = core_web_vitals.get('speed-index', {}).get('numericValue', 0) / 1000
        cls = core_web_vitals.get('cumulative-layout-shift', {}).get('numericValue', 0)

        return {
            'URL': url,
            'Performance Score': performance_score,
            'SEO Score': seo_score,
            'PWA Score': pwa_score,
            'Load Time (seconds)': load_time,
            'First Contentful Paint (seconds)': fcp,
            'Largest Contentful Paint (seconds)': lcp,
            'Total Blocking Time (seconds)': ttb,
            'Speed Index (seconds)': speed_index,
            'Cumulative Layout Shift (CLS)': cls,
            'Strategy': strategy,
            'Status': 'Success'
        }
    except KeyError as e:
        print(f"Error extracting metrics for {url}: {e}")
        return {'URL': url, 'Status': 'Failed', 'Report Link': url_encoded}

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
def check_urls_in_excel(input_excel_file, output_excel_file, max_workers=10):  # Reduced max_workers
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

# Function to crawl a website and collect all the URLs
def crawl_website(start_url, domain, all_urls=None):
    if all_urls is None:
        all_urls = set()

    to_crawl = [start_url]

    while to_crawl:
        url = to_crawl.pop(0)

        if url in all_urls:
            continue

        print(f"Crawling {url}...")
        links = extract_links(url)
        all_urls.add(url)

        for link in links:
            full_url = urljoin(url, link)
            if domain in urlparse(full_url).netloc:
                to_crawl.append(full_url)

        time.sleep(0.5)  # Increased sleep time to slow down crawling speed

    return all_urls

# Function to save results to an Excel file
def save_to_excel(urls, output_file):
    df = pd.DataFrame(list(urls), columns=["URL"])
    df.to_excel(output_file, index=False, engine='openpyxl')
    print(f"Saved {len(urls)} URLs to {output_file}")

# Function to save PageSpeed Insights results to Excel
def save_results_to_excel(results, filename):
    df = pd.DataFrame(results)
    df.to_excel(filename, index=False)
    print(f"Saved PageSpeed Insights to {filename}")

# Main function to process crawling, 404 check, and PageSpeed Insights
async def main():
    start_url = input("Enter the website URL: ")
    domain = urlparse(start_url).netloc
    api_key = input("Enter your Google PageSpeed API key: ")

    # Step 1: Crawl the website to extract all URLs
    all_urls = crawl_website(start_url, domain)
    print(f"Extracted {len(all_urls)} URLs from {start_url}.")

    # Step 2: Check each URL for 404 redirects
    output404_file = 'output404resurrection.xlsx'
    to_check = all_urls.copy()
    to_check_404 = []

    # Reduced max_workers for slower 404 checking
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(check_404, url) for url in to_check]
        for future in as_completed(futures):
            url, status = future.result()
            if status == "Redirects to 404":
                to_check_404.append(url)

    if to_check_404:
        save_to_excel(to_check_404, output404_file)

    # Step 3: Fetch PageSpeed Insights for non-404 URLs
    output_pagespeed_file = 'output_introspection.xlsx'
    to_check_pagespeed = [url for url in all_urls if url not in to_check_404]
    results = []

    if to_check_pagespeed:
        async with aiohttp.ClientSession() as session:
            semaphore = asyncio.Semaphore(10)  # Reduced concurrency
            tasks = []
            for url in to_check_pagespeed:
                tasks.append(fetch_pagespeed_insights_async(url, session, api_key, "desktop", semaphore))

            results = await asyncio.gather(*tasks)

    save_results_to_excel(results, output_pagespeed_file)

# Run the main function
if __name__ == "__main__":
    asyncio.run(main())