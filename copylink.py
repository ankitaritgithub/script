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
            response = requests.get(url, headers=headers, timeout=10)
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

# Function to get detailed page speed insights
def get_page_speed_insights(url, api_key):
    api_url = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={url}&key={api_key}"
    try:
        response = requests.get(api_url)
        if response.status_code == 200:
            data = response.json()
            metrics = data['lighthouseResult']['audits']
            result = {
                'URL': url,
                'Performance Score': metrics['performance']['score'] * 100,  # Convert to percentage
                'First Contentful Paint': metrics['first-contentful-paint']['displayValue'],
                'Largest Contentful Paint': metrics['largest-contentful-paint']['displayValue'],
                'Time to Interactive': metrics['interactive']['displayValue'],
                'Cumulative Layout Shift': metrics['cumulative-layout-shift']['displayValue'],
                'Speed Index': metrics['speed-index']['displayValue']
            }
            return result
        else:
            print(f"Failed to retrieve PageSpeed Insights for {url}: Status code {response.status_code}")
            return {'URL': url}
    except requests.exceptions.RequestException as e:
        print(f"Error occurred while fetching PageSpeed Insights for {url}: {e}")
        return {'URL': url}

# Function to crawl a website and collect all the URLs
def crawl_website(start_url, domain):
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
            if domain in urlparse(full_url).netloc and full_url not in all_urls:
                to_crawl.append(full_url)

        time.sleep(0.5)  # Control the crawling speed

    return all_urls

# Main function to process crawling, 404 checks, and page speed insights
def main():
    start_url = input("Enter the website URL: ")
    api_key = input("Enter your Google PageSpeed Insights API key: ")
    domain = urlparse(start_url).netloc

    # Step 1: Crawl the website to extract all URLs
    all_urls = crawl_website(start_url, domain)
    print(f"Extracted {len(all_urls)} URLs from {start_url}.")

    # Step 2: Check for 404 redirects
    output404_file = 'output404resurrection.xlsx'
    to_check_404 = []

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(check_404, url) for url in all_urls]
        for future in as_completed(futures):
            url, status = future.result()
            if status == "Redirects to 404":
                to_check_404.append(url)

    if to_check_404:
        print(f"Found {len(to_check_404)} URLs that redirect to 404.")

    # Step 3: Fetch PageSpeed Insights for all URLs
    outputinsight_file = 'outputinsight.xlsx'
    speed_results = []

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(get_page_speed_insights, url, api_key) for url in all_urls]
        for future in as_completed(futures):
            result = future.result()
            speed_results.append(result)

    # Save PageSpeed results to Excel
    df_speed = pd.DataFrame(speed_results)
    df_speed.to_excel(outputinsight_file, index=False, engine='openpyxl')
    print(f"Saved PageSpeed Insights results to {outputinsight_file}")

# Run the main function
if __name__ == "__main__":
    main()
