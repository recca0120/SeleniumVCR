from seleniumwire import webdriver

from vcr import PathNamingStrategy, VCR, FilesystemRecorder

vcr = VCR(PathNamingStrategy(), FilesystemRecorder("vcr/refurbished"))

driver = webdriver.Chrome()

driver.request_interceptor = lambda request: vcr.replay(request)
driver.response_interceptor = lambda request, response: vcr.record(request, response)

driver.get("https://www.apple.com/tw/shop/refurbished/mac")

driver.quit()
