import os
import requests
import json
import os
import sys
import requests
import msal
from azure.keyvault.secrets import SecretClient
from azure.identity import ClientSecretCredential
import openai
import json
import re

# Get command line arguments
input_dir              = sys.argv[1]
output_dir             = sys.argv[2]
key_vault_url          = sys.argv[3]
openai_key_secret_name = sys.argv[4]
reject_dir             = sys.argv[5]

# Read Windows Service Principal parameters from environment variables
tenant_id = os.environ.get("PT_TENANT_ID")
client_id = os.environ.get("PT_CLIENT_ID")
client_secret = os.environ.get("PT_CLIENT_SECRET")

# Create a credential object using MSAL for Python
credential    = ClientSecretCredential(tenant_id, client_id, client_secret)
secret_client = SecretClient(vault_url=key_vault_url, credential=credential)

openai_key_secret  = secret_client.get_secret(openai_key_secret_name)
openai.api_type    = "azure"
openai.api_base    = "https://dohoneyai.openai.azure.com/openai/deployments/text-davinci-003/completions?api-version=2022-12-01"
openai.api_version = "2022-12-01"
openai.api_key     = openai_key_secret.value

def noComments(rem,my_string):
  return re.sub(".*"+rem+".*\n?","",my_string)

# Read input files into dictionary
file_list = {}
for filename in os.listdir(input_dir):
    input_file_path = os.path.join(input_dir, filename)
    with open(input_file_path, "r") as input_file:
        file_contents = input_file.read()
        no_comments = noComments("rem",file_contents)
        file_list[filename] = no_comments

# Process input files
for filename, file_contents in file_list.items():
    output_file = os.path.join(output_dir, f"{filename}.sh")
    output_file_path = output_file.replace(".bat", "")

    p_data = "Translate to linux bash: " + file_contents;
    myStr = json.dumps(p_data, ensure_ascii=True)

    if len(p_data) > 4096:
        openai_max_tokens = 1
    else:
      openai_max_tokens = 4096 - len(p_data)

    if openai_max_tokens == 1:
       # save file to reject folder
         reject_file_path = os.path.join(reject_dir, f"{filename}")
         with open(reject_file_path, "w") as reject_file:
            reject_file.write("REM ******************************************************************\n")
            reject_file.write("REM ***  File too large to process ***\n")
            reject_file.write("REM ******************************************************************\n")
            reject_file.write(file_contents)
            continue
    
    openai_payload = {
        "prompt": p_data,
        "max_tokens": openai_max_tokens
    }
    openai_headers = {"Content-Type": "application/json", "api-key": f"{openai.api_key}"}
    openai_response = requests.post(openai.api_base, headers=openai_headers, json=openai_payload )

    if openai_response.status_code != 200:
        print(f"OpenAI API call failed: {openai_response.text}")
        reject_file_path = os.path.join(reject_dir, f"{filename}")
        with open(reject_file_path, "w") as reject_file:
          reject_file.write("******************************************************************")
          reject_file.write(openai_response.text)
          reject_file.write("******************************************************************\n")
          reject_file.write(file_contents)
        continue    

    p_data = openai_response.json()
    resp_text =  json.loads(openai_response.text)
    p_data = resp_text['choices'][0]['text']

    # Write translated file contents to output file
    with open(output_file_path, "w") as output_file:
        output_file.write("#!/bin/bash\n")
        output_file.write(p_data)