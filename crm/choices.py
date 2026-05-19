# crm/choices.py

# Custom ForeignKey matching fields per related model
CUSTOM_FK_MATCH_FIELDS = {
    'auth.User': ['username', 'email', 'first_name'],
    'crm.Bank': ['name'],
    'crm.LoanProduct': ['name'],
    'crm.Branch': ['branch_name'],
    'crm.Agent': ['agent_code', 'name'],
    # Add others as needed
}

# User Profile Model with Role
# ROLE_CHOICES = [
#         ('Admin', 'Admin'),
#         ('TL', 'Team Leader'),
#         ('TSE', 'Tele Sales Executive'),
#         ('Hr Executive','Hr Executive'),
#         ('Other', 'Other'),
#     ]
AGREEMENT_STATUS_CHOICES = [
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('terminated', 'Terminated'),
    ]

COMPANY_CATEGORY_CHOICES = [
    ('A', 'National'),
]

QUALIFICATION_CHOICES = [
    ('10th', '10th'),
    ('12th', '12th'),
    ('Graduation', 'Graduation'),
    ("Bachelor's", "Bachelor's"),
    ("Master's", "Master's"),
    ('Ph.D', 'Ph.D'),
    ('CA', 'CA'),
    ('CS', 'CS'),
    ('CMA', 'CMA'),
    ('ITI', 'ITI'),
    ('Polytechnic Diplomas', 'Polytechnic Diplomas'),
]

WORK_TYPE_CHOICES = [
    ('WFH', 'WFH'),
    ('Regular', 'Regular'),
    ('Other', 'Other'),
]
EMPLOYMENT_TYPE_CHOICES = [
    ('Self-Employed', 'Self-Employed'),
    ('Salaried', 'Salaried'),
]
INDUSTRY_PROFESSION_CHOICES = [
    ('ITES', 'ITES'),
    ('Technology', 'Technology'),
    ('Manufacturing', 'Manufacturing'),
    ('Retail', 'Retail'),
    ('Sales', 'Sales'),
    ('Banking/Finance/NBFC/INSURANCE', 'Banking/Finance/NBFC/INSURANCE'),
    ('Recovery', 'Recovery'),
    ('Manpower', 'Manpower'),
    ('Trading', 'Trading'),
    ('Software', 'Software'),
    ('Medical/Hospital', 'Medical/Hospital'),
    ('Education/School/College/University', 'Education/School/College/University'),
    ('State Govt', 'State Govt'),
    ('Central Govt', 'Central Govt'),
    ('Other Profession', 'Other Profession'),
]
MODE_OF_SALARY_CHOICES = [
    ('Cash', 'Cash'),
    ('Cheque', 'Cheque'),
    ('NEFT', 'NEFT'),
    ('IMPS', 'IMPS'),
]
PROCESS_CHOICES = [
    ('OD', 'OD'),
    ('AL', 'AL'),
    ('PL', 'PL'),
    ('BL', 'BL'),
    ('HL', 'HL'),
]
DEPARTMENT_CHOICES = [
    ('HR', 'HR'),
    ('Finance', 'Finance'),
    ('Sales', 'Sales'),
    ('Marketing', 'Marketing'),
    ('Operations', 'Operations'),
    ('Customer Service', 'Customer Service'),
    ('IT', 'IT'),
    ('Legal', 'Legal'),
    ('Procurement', 'Procurement'),
    ('Administration', 'Administration'),
    ('Other', 'Other'),
]

GENDER_CHOICES =( ('M','Male'),('F','Female') )
MARITAL_STATUS_CHOICES =( ('Married','Married'),('Unmarried','Unmarried') )
RESIDENCE_TYPE_CHOICES = ( ('Owned','Owned'),('Rented','Rented') ) 
COMPANY_TYPE_CHOICES = [
        ('Private', 'Private'),
        ('Public', 'Public'),
        ('Government', 'Government'),
        ('Partnership', 'Partnership'),
        ('Sole-Proprietorship', 'Sole Proprietorship'),
        ('Self-employed', 'Self-employed'),
        ('Other', 'Other'),
    ]
COMPANY_LISTING_CHOICES = [
    ('CAT D', 'CAT D'),
    ('CAT C', 'CAT C'),
    ('CAT B', 'CAT B'),
    ('CAT A', 'CAT A'),
    ('Super CAT A', 'Super CAT A'),
    ('Govt Emp', 'Govt Emp'),
    ('Open Market', 'Open Market'),
    ('Unlisted', 'Unlisted'),
]


LEAD_TYPE_CHOICES = [
    ('Fresh Lead', 'Fresh Lead'),
    ('Referral', 'Referral'),
    ('Online Enquiry', 'Online Enquiry'),
    ('Walk-in', 'Walk-in'),
    ('Telecalling', 'Telecalling'),
    ('Revisit', 'Revisit'),
    ('Repeat Customer', 'Repeat Customer'),
    ('Partner Channel', 'Partner Channel'),
    ('Bank Transfer', 'Bank Transfer'),
    ('Purchased Data', 'Purchased Data'),
]

LEAD_STATUS_CHOICES = [
    ('new', 'New'),
    ('Future Lead', 'Future Lead'),
    ('follow_up', 'Follow-UP'),
    ('waiting_for_docs', 'Waiting For Docs'),
    ('OTP', 'OTP'),
    ('Ringing', 'Ringing'),
    ('Not_Interested', 'Not Interested'),
    ('loan_needed', 'Loan Needed'),
    ('Switched_Off', 'Switched Off'),
    ('invalid_number', 'Invalid Number'),

    # Card Process Status
    ('Approved', 'Approved'),
    ('VKYC Pending', 'VKYC Pending'),
    ('Bio Pending', 'Bio Pending'),
    ('KYC Done', 'KYC Done'),
    ('Curing', 'Curing'),
    ('WIP', 'WIP'),
    ('Card Out', 'Card Out'),
]

CALL_LOG_STATUS_CHOICES = [
    ('new', 'New'),
    ('interested', 'Interested'),
    ('waiting_for_docs', 'Waiting For Docs'),
    ('follow_up', 'Follow UP'),
    ('call_back', 'Call Back'),
    ('not_eligible', 'Not Eligible'),
    ('not_interested', 'Not Interested'),
    # ('ofb', 'OFB'),
    ('OTP', 'OTP'),
    ('Scorecard Approved','Scorecard Approved'),
    # ('underwriting', 'Underwriting'),
    ('reject', 'Reject'),
    # ('reject_relook', 'Reject Relook'),
    # ('approved', 'Approved'),
    # ('approved_hold', 'Approved Hold'),
    ('hold', 'Hold'),
    # ('disbursed', 'Disbursed'),
    ('Future Lead', 'Future Lead'),
    # ('UW Hold','UW Hold'),
    ('Declined','Declined'),
    # Newly added status
    ('Ringing','Ringing'),
    ('Switched_Off', 'Switched Off'),
    ('invalid_number', 'Invalid Number'),
    
    ("initiated", "Initiated"),
    ("connected", "Connected"),
    ("missed", "Missed"),
    ("failed", "Failed"),
]

CHANNEL_CHOICES = [
    ('APIS', 'APIS'),
    ('FINBROS', 'Finbros'),
    ('FAST', 'Fast'),
    ('PAISA_EXPO', 'Paisa Expo'),
    ('Finwizz', 'Finwizz'),
    ('Finbud', 'Finbud'),
    ('StarPower', 'StarPower'),
    ('Cateye','Cateye'),
    ('Profincare','Profincare'),
]

LOAN_TYPE_CHOICES = [
    ('FRESH', 'Fresh'),
    ('BT', 'BT'),
    ('OD', 'OD'),
    ('TOPUP', 'Top UP'),
]


CANDIDATE_STATUS_CHOICES = [
    ("New", "New"),
    ("Contacted", "Contacted"),
    ("Ringing", "Ringing"),
    ("Interview Scheduled", "Interview Scheduled"),
    ("Interviewed", "Interviewed"),
    ("Shortlisted", "Shortlisted"),
    # ("Selected", "Selected"),
    # ("Offer Released", "Offer Released"),
    # ("Offer Accepted", "Offer Accepted"),
    # ("Offer Declined", "Offer Declined"),
    # ("Joined", "Joined"),
    # ("No Show (Interview)", "No Show (Interview)"),
    # ("No Show (Joining)", "No Show (Joining)"),
    ("On Hold", "On Hold"),
    ("Rejected", "Rejected"),
    #("Withdrawn", "Withdrawn"),
    ("Blacklisted", "Blacklisted"),
    ("Not Interested","Not Interested"),
    ("Switched Off","Switched Off"),
    ("Invalid Number","Invalid Number"),
    ("Hike Expectation", "Hike Expectation"),
]
DESIGNATION_CHOICES = [
    ("Backend Executive", "Backend Executive"),
    ("HR Executive", "HR Executive"),
    ("Team Leader", "Team Leader"),
    ("Sales Manager", "Sales Manager"),
    ("Tele Sales Executive", "Tele Sales Executive"),
    ("Trainer", "Trainer"),
    ("Quality Analyst", "Quality Analyst"),
    ("MIS Executive", "MIS Executive"),
    ("HR Manager", "HR Manager"),
    ("Customer Care Executive", "Customer Care Executive"),
    ("Business Manager", "Business Manager"),
    ("Business Head", "Business Head"),
    ("CEO", "CEO"),
    ("Director", "Director"),
    ("House Keeping", "House Keeping"),
    ("IT Support Engineer", "IT Support Engineer"),
]

INTERVIEW_STATUS_CHOICES = [
    ("Scheduled", "Scheduled"),
    # ("Completed", "Completed"),
    ("Selected", "Selected"),
    ("Rejected", "Rejected"),
    ("On Hold", "On Hold"),
    # ("No Show", "No Show"),
    ("Rescheduled", "Rescheduled"),
    ("Canceled", "Canceled"),
]

EMPLOYMENT_STATUS_CHOICES = [
    ("Exit Completed", "Exit Completed"),
    ("Resigned", "Resigned"),
    ("Active", "Active"),
    ("Notice Period", "Notice Period"),
    ("Absconded","Absconded"),
    ("Terminated","Terminated")
]
CANDIDATE_TRAINING_STATUS_CHOICE = [
    ("In Process", "In Process"),
    ("Completed", "Completed"),
    ("Not Started", "Not Started"),
    ("On Hold", "On Hold"),
    ("Dropped Out", "Dropped Out"),
    ("Rejected By Trainer","Rejected By Trainer")
]

CANDIDATE_SOURCE_CHOICE = [
    ("Referral", "Referral"),
    ("Apna Job", "Apna Job"),
    ("WorkIndia", "WorkIndia"),
    ("Social Media", "Social Media"),
    ("Company Website", "Company Website"),
]

CANDIDATE_DEPARTMENT_CHOICE = [
    ("Operations", "Operations"),
    ("Customer Support", "Customer Support"),
    ("Sales", "Sales"),
    ("HR", "HR"),
    ("Training", "Training"),
    ("IT Support", "IT Support"),
]

CANDIDATE_POSITION_APPLIED_CHOICE = [
    ("Customer Care Executive", "Customer Care Executive"),
    ("Tele Sales Executive","Tele Sales Executive"),
    ("Team Leader", "Team Leader"),
    ("Sales Manager", "Sales Manager"),
    ("Quality Analyst", "Quality Analyst"),
    ("Trainer", "Trainer"),
    ("MIS Executive", "MIS Executive"),
    ("HR Executive", "HR Executive"),
    ("House Keeping", "House Keeping"),
]

REASON_FOR_RESIGNATION_CHOICES = [
    ("Better Opportunity", "Better Opportunity"),
    ("Personal Reasons", "Personal Reasons"),
    ("Higher Education", "Higher Education"),
    ("Work-Life Balance", "Work-Life Balance"),
    ("Relocation", "Relocation"),
    ("Lack of Growth", "Lack of Growth"),
    ("Salary Issues", "Salary Issues"),
    ("Company Culture", "Company Culture"),
    ("Conflict with Management", "Conflict with Management"),
    ("Contract Ended", "Contract Ended"),
    ("Joining Family Business", "Joining Family Business"),
]

INDUSTRY_CHOICES = [
    ("Banking & Finance", "Banking & Finance"),
    ("Information Technology", "Information Technology"),
    ("Telecommunication", "Telecommunication"),
    ("Retail & E-Commerce", "Retail & E-Commerce"),
    ("Healthcare", "Healthcare"),
    ("Education & EdTech", "Education & EdTech"),
    ("Call Centers", "Call Centers"),
    ("Manufacturing", "Manufacturing"),
    ("Real Estate", "Real Estate"),
    ("Hospitality & Tourism", "Hospitality & Tourism"),
    ("Automobile", "Automobile"),
    ("Logistics & Supply Chain", "Logistics & Supply Chain"),
    ("Media & Advertising", "Media & Advertising"),
    ("Legal & Compliance", "Legal & Compliance"),
    ("Government", "Government"),
]
BLOOD_GROUP_CHOICES = [
    ("A+", "A+"),
    ("A-", "A-"),
    ("B+", "B+"),
    ("B-", "B-"),
    ("AB+", "AB+"),
    ("AB-", "AB-"),
    ("O+", "O+"),
    ("O-", "O-"),
]

INDIAN_STATES = [
    ('AP', 'Andhra Pradesh'),
    ('AR', 'Arunachal Pradesh'),
    ('AS', 'Assam'),
    ('BR', 'Bihar'),
    ('CG', 'Chhattisgarh'),
    ('GA', 'Goa'),
    ('GJ', 'Gujarat'),
    ('HR', 'Haryana'),
    ('HP', 'Himachal Pradesh'),
    ('JH', 'Jharkhand'),
    ('KA', 'Karnataka'),
    ('KL', 'Kerala'),
    ('MP', 'Madhya Pradesh'),
    ('MH', 'Maharashtra'),
    ('MN', 'Manipur'),
    ('ML', 'Meghalaya'),
    ('MZ', 'Mizoram'),
    ('NL', 'Nagaland'),
    ('OD', 'Odisha'),
    ('PB', 'Punjab'),
    ('RJ', 'Rajasthan'),
    ('SK', 'Sikkim'),
    ('TN', 'Tamil Nadu'),
    ('TS', 'Telangana'),
    ('TR', 'Tripura'),
    ('UP', 'Uttar Pradesh'),
    ('UK', 'Uttarakhand'),
    ('WB', 'West Bengal'),
    ('AN', 'Andaman and Nicobar Islands'),
    ('CH', 'Chandigarh'),
    ('DN', 'Dadra and Nagar Haveli and Daman and Diu'),
    ('DL', 'Delhi'),
    ('JK', 'Jammu and Kashmir'),
    ('LA', 'Ladakh'),
    ('LD', 'Lakshadweep'),
    ('PY', 'Puducherry'),
]


OPERATORS = [
    ("eq", "Equals"),
    ("neq", "Not equals"),
    ("lt", "Less than"),
    ("gt", "Greater than"),
    ("lte", "Less than or equal to"),
    ("gte", "Greater than or equal to"),
    ("contains", "Contains"),
    ("startswith", "Starts with"),

    # Multi-value operator
    ("in", "In (multiple values)"),
    ("not_in", "Not in (multiple values)"),

    # NULL checks
    ("is_null", "Is empty"),
    ("is_not_null", "Is not empty"),

    # Date specific operators
    ("today", "Today"),
    ("yesterday", "Yesterday"),
    ("tomorrow", "Tomorrow"),
    ("7_days", "Last 7 Days"),
    ("30_days", "Last 30 Days"),
    ("this_month", "This Month"),
    ("last_month", "Last Month"),
]

VISIBILITY_CHOICES = [
        ("private", "Visible only to me"),
        ("public", "Visible to all"),
        ("groups", "Visible to certain groups"),
    ]