import requests
from bs4 import BeautifulSoup

url = "http://www.yelp.com/search?find_desc={0}&find_loc=6+Metrotech+Ctr,+Brooklyn,+NY&start={1}"
response = requests.get(url.format("japanese", 0))
soup = BeautifulSoup(response.content)
results = soup.find_all("li", {"class": "regular-search-result"})
for result in results:
    print result.find("span", {"class": "business-attribute price-range"}).string
