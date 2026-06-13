import requests

url = "https://api-smartflo.tatateleservices.com/v1/click_to_call"

payload = {
    "async": 1,
    "agent_number": "0607621620002",
    "destination_number": " 8102925458",
    "caller_id": "918069879661"
}
headers = {
    "accept": "application/json",
    "Authorization": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwczovL2Nsb3VkcGhvbmUudGF0YXRlbGVzZXJ2aWNlcy5jb20vYXBpL3YxL2F1dGgvbG9naW4iLCJpYXQiOjE3NzgwNTU4OTksImV4cCI6MTc3ODA1OTQ5OSwibmJmIjoxNzc4MDU1ODk5LCJqdGkiOiI4eEFVSmdQSUs0cjd1blFaIiwic3ViIjoiNzYyMTYyIiwiY2xpZW50X2lkIjo3NjIxNjIsImNyIjpmYWxzZX0.0Or73Q4gasLoeBggqGgv-7EmYkXKhrmf_8vpkqBkz7s",
    "content-type": "application/json"
}

response = requests.post(url, json=payload, headers=headers)

print(response.text)

