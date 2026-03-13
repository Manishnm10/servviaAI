import requests
import json

url_identify = 'http://localhost:9000/api/lab-report/identify/'
url_confirm = 'http://localhost:9000/api/lab-report/confirm/'

print('--- STEP 1: IDENTIFY ---')
files = {'report': open(r'C:\Users\cools\servviaAI\servvia\Report-26JC1506055_Razak_K.M_PJPDLAB_12Mar2026_132003.pdf', 'rb')}
data = {'email_id': 'mr.razak.test@example.com'}

resp1 = requests.post(url_identify, files=files, data=data)
print(json.dumps(resp1.json(), indent=2))

report_id = resp1.json().get('pending_report_id')

if report_id:
    print('\n--- STEP 2: CONFIRM ---')
    payload = {
        'pending_report_id': report_id,
        'create_profile': True,
        'profile_label': 'Dad Health'
    }
    resp2 = requests.post(url_confirm, json=payload)
    print(json.dumps(resp2.json(), indent=2))
