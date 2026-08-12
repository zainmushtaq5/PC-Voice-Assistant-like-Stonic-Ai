import urllib.request
import zipfile
import os
import ssl

ssl._create_default_https_context = ssl._create_unverified_context

url = "https://alphacephei.com/vosk/models/vosk-model-en-us-0.22-lgraph.zip"
out_zip = "models/vosk-model-en-us-0.22-lgraph.zip"
out_dir = "models"

print("Downloading " + url + " ...")
urllib.request.urlretrieve(url, out_zip)
print("Extracting...")
with zipfile.ZipFile(out_zip, 'r') as zip_ref:
    zip_ref.extractall(out_dir)
print("Done.")
