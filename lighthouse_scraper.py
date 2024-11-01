import os
import subprocess
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup


from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

def setup_driver():
    chrome_options = webdriver.ChromeOptions()
    # Add any necessary options here
    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chrome_options)
    return driver


# Function to set up Selenium WebDriver
# def setup_driver():
#     chrome_options = Options()
#     chrome_options.add_argument("--headless")  # Run in headless mode
#     chrome_service = Service(executable_path='/path/to/chromedriver')  # Update path to your chromedriver
#     driver = webdriver.Chrome(service=chrome_service, options=chrome_options)
#     return driver

# Function to fetch links from the specified section
def fetch_links_from_section(url, section_selector):
    driver = setup_driver()
    driver.get(url)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    driver.quit()

    sections = soup.select(section_selector)
    url_list = []
    if sections:
        for section in sections:
            links = section.find_all('a', href=True)
            url_list.extend(link['href'] for link in links)
        return url_list
    else:
        print(f"No sections found with selector: {section_selector}")
        return []

# Function to run Lighthouse and get metrics
def run_lighthouse(url):
    report_file = f'lighthouse_report_{url.replace("https://", "").replace("/", "_")}.html'
    command = f'lighthouse {url} --output html --output-path {report_file} --chrome-flags="--headless"'

    try:
        subprocess.run(command, shell=True, check=True)
        return report_file
    except subprocess.CalledProcessError as e:
        print(f"Error running Lighthouse for {url}: {e}")
        return None

# Function to extract metrics from Lighthouse report
def extract_metrics_from_report(report_file):
    with open(report_file, 'r') as file:
        soup = BeautifulSoup(file, 'html.parser')

    performance_score = float(soup.find("span", class_="lh-metric__score").text) * 100  # Example extraction
    seo_score = ...  # Extract SEO score similarly
    # Add extraction logic for other metrics as needed

    report_link = f'file://{os.path.abspath(report_file)}'  # Link to the report file

    return {
        'Performance Score': performance_score,
        'SEO Score': seo_score,
        'Report Link': report_link
    }

# Function to save results to Excel
def save_results_to_excel(results, filename):
    df = pd.DataFrame(results)
    df.to_excel(filename, index=False)

# Main function to coordinate everything
def main():
    url = 'https://www.xenonstack.com/blog/tag/enterprise-ai'
    section_selector = 'h3.card-title'

    urls = fetch_links_from_section(url, section_selector)
    print(f"Fetched {len(urls)} URLs.")

    results = []
    for url in urls:
        print(f"Running Lighthouse for {url}...")
        report_file = run_lighthouse(url)
        if report_file:
            metrics = extract_metrics_from_report(report_file)
            metrics['URL'] = url
            results.append(metrics)

    output_file = 'lighthouse_results.xlsx'
    save_results_to_excel(results, output_file)
    print(f"Results saved to {output_file}.")

if __name__ == "__main__":
    main()
