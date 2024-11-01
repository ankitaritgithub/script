from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

# Function to fetch PageSpeed Insights data for a given URL
def fetch_page_speed_insights(url):
    # Set up Chrome options
    chrome_options = Options()
    # chrome_options.add_argument("--headless")  # Optional: run in headless mode
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    # Specify the path to ChromeDriver using ChromeDriverManager
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    try:
        # Open the Google PageSpeed Insights page
        driver.get("https://developers.google.com/speed/pagespeed/insights/")

        # Find the input box and enter the URL
        input_box = driver.find_element(By.CSS_SELECTOR, "#i4")
        input_box.clear()
        input_box.send_keys(url)

        # Click the Analyze button
        analyze_button = driver.find_element(By.CSS_SELECTOR, "#yDmH0d > c-wiz > div.T4LgNb > div > div.ZVTDqc > form > div.VfPpkd-dgl2Hf-ppHlrf-sM5MNb > button > span")
        analyze_button.click()

        # Wait for results to load
        WebDriverWait(driver, 60).until(
            EC.visibility_of_element_located((By.XPATH, "//div[contains(@class, 'lh-gauge__percentage')]"))
        )

        # Fetch the performance score and other metrics
        performance_score = driver.find_element(By.XPATH, "//div[contains(@class, 'lh-gauge__percentage')]").text
        first_contentful_paint = driver.find_element(By.CSS_SELECTOR, "#first-contentful-paint .lh-metric__value").text        # speed_index = driver.find_element(By.CSS_SELECTOR, "div[data-metric-id='3'] .lh-metric__value").text
        # largest_contentful_paint = driver.find_element(By.CSS_SELECTOR, "div[data-metric-id='4'] .lh-metric__value").text
        # time_to_interactive = driver.find_element(By.CSS_SELECTOR, "div[data-metric-id='5'] .lh-metric__value").text
        # cumulative_layout_shift = driver.find_element(By.CSS_SELECTOR, "div[data-metric-id='6'] .lh-metric__value").text

        # Print the results
        print(f"URL: {url}")
        print(f"Performance Score: {performance_score}")
        print(f"First Contentful Paint: {first_contentful_paint}")
        # print(f"Speed Index: {speed_index}")
        # print(f"Largest Contentful Paint: {largest_contentful_paint}")
        # print(f"Time to Interactive: {time_to_interactive}")
        # print(f"Cumulative Layout Shift: {cumulative_layout_shift}")
        print("-----")

    finally:
        driver.quit()

# List of URLs to analyze
urls = [
    "https://xenonstack.com",
    "https://google.com",
    # Add more URLs as needed
]

# Fetch PageSpeed Insights for each URL
for url in urls:
    fetch_page_speed_insights(url)
