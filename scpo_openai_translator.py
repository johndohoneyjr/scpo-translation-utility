import openai
from openai.error import RateLimitError
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
import stat
import time

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
openai.api_key     = openai_key_secret.value

# function that strips from the beginning of the string to the value of '```'
def stripHeader(my_string):
    return my_string
    

# function that strips from '```' to the end of the string
def stripFooter(my_string):
    return my_string[:my_string.rfind("```")]
          

def noComments(rem,my_string):
  lines = my_string.split("\n")
  resultString = ""
  # iterate over the lines
  for line in lines:
    # check if the line starts with "REM", "rem", or "Rem"
    if line.strip().lower().startswith(("rem",)):
        # if it does, skip this line
        continue
    resultString += (line + "\n")
  return resultString


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

    r_data = file_contents;
    myStr = json.dumps(r_data, ensure_ascii=True)

    if len(r_data) > 4096:
        openai_max_tokens = 1
    else:
      if(4096 - len(r_data) - 135) < 0:
        openai_max_tokens = 4096 - len(r_data)
      else:
        openai_max_tokens = 4096 - len(r_data) - 135

    if openai_max_tokens == 1:
       # save file to reject folder
         reject_file_path = os.path.join(reject_dir, f"{filename}")
         with open(reject_file_path, "w") as reject_file:
            reject_file.write("REM ******************************************************************\n")
            reject_file.write("REM ***  File too large to process ***\n")
            reject_file.write("REM ******************************************************************\n")
            reject_file.write(file_contents)
            continue
   
    promptsArray = [r_data]
    stringifiedPromptsArray = json.dumps(promptsArray)
    prompts = [
       {"role":"system","content":"Convert Windows Batch script into Linux Bash Scripts."},
       {"role":"system","content":"Exit Status: https://www.geeksforgeeks.org/exit-status-variable-in-linux/"},
       {"role":"system","content":"Save all call exit status,  $?,  into a unique variable before If testing ."},
       {"role":"system","content":"Save exit status into a variable after all sqlplus calls in script."},
       {"role":"system","content":"Use unique variable in all output processing."},
       {"role": "user","content": stringifiedPromptsArray}
    ]

    batchInstruction = {"role":"system","content":"Follow all instructions in system content and user content into executable Linux BASH script"}
    prompts.append(batchInstruction)

    while True:
       
       try:
        stringifiedBatchCompletion = openai.ChatCompletion.create(
          model="gpt-3.5-turbo",
          messages=prompts,
          max_tokens=openai_max_tokens)
       except RateLimitError as e:
        # Handle the RateLimitError exception
        print("OpenAI API rate limit exceeded. Retrying in 90 seconds...")
        print("Exception details:", e)
        print("Sleeping 60 seconds to clear RateLimitError...")
        # Sleep for 90 seconds before retrying
        time.sleep(90)
        continue
       else:
          batchCompletion = json.loads(str(stringifiedBatchCompletion.choices[0]))
          translated_file = batchCompletion['message']['content']
          stripped_header = stripHeader(translated_file)
          p_data = stripFooter(stripped_header)
          break

    if stringifiedBatchCompletion.choices[0].finish_reason != "stop":
        try:
          print(f"OpenAI API call failed processing: {filename}")
          reject_file_path = os.path.join(reject_dir, f"{filename}")
          with open(reject_file_path, "w") as reject_file:
            reject_file.write("******************************************************************")
            reject_file.write(batchCompletion['message']['content'])
            reject_file.write("******************************************************************\n")
            reject_file.write(file_contents)
            continue   
        except Exception as e:
          reject_file_path = os.path.join(reject_dir, f"{filename}")
          print(f"Error handling exception from file: {reject_file_path}")
          print("Exception Data: {e}")
          continue    

    # Write translated file contents to output file
    with open(output_file_path, "w") as output_file:
        output_file.write(p_data)