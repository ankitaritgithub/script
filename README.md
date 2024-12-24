import time
import requests
import pandas as pd
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed

# Function to extract links from a webpage
def extract_links(url, retries=3):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, "html.parser")
                links = [urljoin(url, link['href']) for link in soup.find_all('a', href=True) if link['href'].startswith('http')]
                return links
            else:
                print(f"Failed to retrieve {url}: Status code {response.status_code}")
                return []
        except requests.exceptions.RequestException as e:
            print(f"Error fetching {url}: {e}")
            time.sleep(2 ** attempt)  # Exponential backoff
    return []

# Asynchronous function to fetch PageSpeed Insights with retry logic
async def fetch_pagespeed_insights(url, session, api_key, strategy, semaphore, retries=3):
    url_encoded = url.replace(":", "%3A").replace("/", "%2F")
    api_url = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={url_encoded}&key={api_key}&strategy={strategy}"

    async with semaphore:
        for attempt in range(retries):
            try:
                async with session.get(api_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        return extract_metrics(data, url, strategy)
                    elif response.status == 500:
                        print(f"Error 500 for {url}, retrying...")
                    else:
                        print(f"Error {response.status} for {url}")
                        return {'URL': url, 'Status': 'Failed', 'Report Link': api_url}
            except Exception as e:
                print(f"Error for {url}: {e}, retrying...")
                await asyncio.sleep(2 ** attempt)
        print(f"Failed to fetch data for {url} after {retries} attempts.")
        return {'URL': url, 'Status': 'Failed', 'Report Link': api_url}

# Function to extract metrics from PageSpeed Insights
def extract_metrics(data, url, strategy):
    try:
        lighthouse = data.get('lighthouseResult', {})
        metrics = {
            'URL': url,
            'Performance Score': lighthouse.get('categories', {}).get('performance', {}).get('score', 0) * 100,
            'SEO Score': lighthouse.get('categories', {}).get('seo', {}).get('score', 0) * 100,
            'PWA Score': lighthouse.get('categories', {}).get('pwa', {}).get('score', 0) * 100,
            'Load Time (s)': lighthouse.get('audits', {}).get('largest-contentful-paint', {}).get('numericValue', 0) / 1000,
            'FCP (s)': lighthouse.get('audits', {}).get('first-contentful-paint', {}).get('numericValue', 0) / 1000,
            'LCP (s)': lighthouse.get('audits', {}).get('largest-contentful-paint', {}).get('numericValue', 0) / 1000,
            'TTB (s)': lighthouse.get('audits', {}).get('total-blocking-time', {}).get('numericValue', 0) / 1000,
            'Speed Index (s)': lighthouse.get('audits', {}).get('speed-index', {}).get('numericValue', 0) / 1000,
            'CLS': lighthouse.get('audits', {}).get('cumulative-layout-shift', {}).get('numericValue', 0),
            'Strategy': strategy,
            'Status': 'Success'
        }
        return metrics
    except KeyError as e:
        print(f"Error extracting metrics for {url}: {e}")
        return {'URL': url, 'Status': 'Failed'}

# Function to check if a URL redirects to a 404 page
def check_404(url):
    try:
        response = requests.get(url, timeout=10)
        return (url, "Redirects to 404" if response.status_code == 404 else "Pass")
    except requests.exceptions.RequestException as e:
        print(f"Error checking {url}: {e}")
        return (url, "Error")

# Function to perform 404 check on URLs from an Excel file
def check_urls_in_excel(input_file, output_file, max_workers=10):
    df = pd.read_excel(input_file)
    urls = df['URL'].dropna().tolist()
    result = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(check_404, url): url for url in urls}
        for future in as_completed(futures):
            url, status = future.result()
            result.append((url, status))

    df['Status'] = df['URL'].apply(lambda x: dict(result).get(x, ""))
    df.to_excel(output_file, index=False)
    print(f"Results saved to {output_file}")

# Function to crawl a website and collect all URLs
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
            if domain in urlparse(link).netloc:
                to_crawl.append(link)
        time.sleep(0.5)
    return all_urls

# Function to save URL list to Excel
def save_to_excel(urls, filename):
    df = pd.DataFrame(list(urls), columns=["URL"])
    df.to_excel(filename, index=False, engine='openpyxl')
    print(f"Saved {len(urls)} URLs to {filename}")

# Function to save PageSpeed results to Excel
def save_results_to_excel(results, filename):
    df = pd.DataFrame(results)
    df.to_excel(filename, index=False)
    print(f"PageSpeed Insights saved to {filename}")

# Main function to crawling, 404 checking, and PageSpeed Insights
async def main():
    start_url = input("Enter the website URL: ")
    domain = urlparse(start_url).netloc
    api_key = input("Enter your Google PageSpeed API key: ")

    # Crawl the website to extract URLs
    all_urls = crawl_website(start_url, domain)
    print(f"Extracted {len(all_urls)} URLs from {start_url}.")
    save_to_excel(all_urls, 'crawled_urlspage.xlsx')

    # Check for 404 redirects
    output404_file = 'output404page.xlsx'
    check_urls_in_excel('crawled_urlspage.xlsx', output404_file)

    # Fetch PageSpeed Insights for non-404 URLs
    df = pd.read_excel(output404_file)
    urls_to_check = df[df['Status'] != 'Redirects to 404']['URL'].tolist()
    output_pagespeed_file = 'output_pagespeedpage.xlsx'
    results = []

    async with aiohttp.ClientSession() as session:
        semaphore = asyncio.Semaphore(10)
        tasks = [fetch_pagespeed_insights(url, session, api_key, "desktop", semaphore) for url in urls_to_check]
        results = await asyncio.gather(*tasks)

    save_results_to_excel(results, output_pagespeed_file)

# Run the main function
if __name__ == "__main__":
    asyncio.run(main())
-*************************************************************
work on lighthouse script to  fetch the URL through crawling and next to check the URL redirect page after that for the correct redirect page of each URL fetch the page insight performance report
work on copying the link  of each URL to the performance report script part
work on copying the link  of each URL to the performance report script part
