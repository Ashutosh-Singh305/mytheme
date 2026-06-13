import ipaddress
import re

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.conf import settings
import datetime
from django.utils import timezone
from django.forms import ValidationError
from .choices import *
from simple_history.models import HistoricalRecords
from tinymce.models import HTMLField
from django.db.models import Q

# ---------- Abstract Base Model ----------
class AuditModel(models.Model):
    assigned_to = models.ForeignKey(User,verbose_name="Assigned To", null=True, blank=True, on_delete=models.SET_NULL, related_name="%(class)s_assigned")
    created_by = models.ForeignKey(User, verbose_name="Created By", null=True, on_delete=models.CASCADE, related_name="%(class)s_created_by")
    created_date = models.DateTimeField(("Created Date"),auto_now_add=True)
    modified_by = models.ForeignKey(User, verbose_name="Modified By",null=True, on_delete=models.CASCADE, related_name="%(class)s_modified_by")
    modified_at = models.DateTimeField(("Modified At"),auto_now=True)
    class Meta:
        abstract = True

class IPRange(AuditModel):
    start_ip = models.GenericIPAddressField(
        verbose_name="Start IP Address"
    )
    end_ip = models.GenericIPAddressField(
        verbose_name="End IP Address"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Is Active"
    )

    class Meta:
        verbose_name = "IP Range"
        verbose_name_plural = "IP Ranges"

    def clean(self):
        """
        Validate:
        1. Proper IP format
        2. Start IP <= End IP
        """
        try:
            start = ipaddress.ip_address(self.start_ip)
            end = ipaddress.ip_address(self.end_ip)
        except ValueError:
            raise ValidationError("Invalid IP address format")

        if start > end:
            raise ValidationError({
                "start_ip": "Start IP must be less than or equal to End IP",
                "end_ip": "End IP must be greater than or equal to Start IP",
            })

    def save(self, *args, **kwargs):
        # Ensure validation always runs
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.start_ip} - {self.end_ip}"

# ---------- Validators ----------
phone_regex = RegexValidator(
    regex=r'^\d{10}$',
    message="Phone number must be exactly 10 digits."
)
# By Ashutosh on 26 March 2026
class Branch(AuditModel):
    # basic info
    name = models.CharField(max_length=100, null=True, blank=True,unique=True,verbose_name="Branch Name")
    code = models.CharField(max_length=20, null=True, blank=True,unique=True,verbose_name="Branch Code")
    gstin = models.CharField(max_length=15, null=True, blank=True,unique=True,verbose_name="GSTIN")
    isActive = models.BooleanField(default=True,verbose_name="Is Active")
    
    # Address fields
    address = models.TextField(null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    state = models.CharField("State", max_length=50, choices=INDIAN_STATES, blank=True, null=True)
    pincode = models.CharField(max_length=6, null=True, blank=True)

    # Contact fields
    branch_head = models.ForeignKey(User,on_delete=models.SET_NULL, null=True, blank=True,verbose_name="Branch Head")
    email = models.EmailField(null=True, blank=True,verbose_name="Email ID")  
    mobile = models.CharField(max_length=20, null=True, blank=True,verbose_name="Mobile Number", validators=[phone_regex]) 


    def save(self, *args, **kwargs):
        if not self.code:
            super().save(*args, **kwargs)  # save first to get ID
            self.code = f"AP{str(self.id).zfill(3)}"
            return super().save(update_fields=["code"])
        return super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.name} - {self.get_state_display()}" or "Unnamed Branch"

      

class UserProfile(AuditModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    emp_code = models.CharField(("Employee Code"),max_length=20, unique=True, null=True, blank=True)
    role = models.CharField(max_length=50, choices=ROLE_CHOICES,null=True ,blank=True)
    manager = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='subordinates')
    branch = models.ForeignKey(Branch, null=True, blank=True, on_delete=models.SET_NULL,related_name="branch_user")
    def __str__(self):
        return f"{self.user.username} - {self.role}"



# Define Field Access Control Model
class FieldAccessControl(AuditModel):
    role = models.CharField(max_length=50, choices=ROLE_CHOICES,null=True ,blank=True)
    model_name = models.CharField(max_length=50,null=True, blank=True)
    field_name = models.CharField(max_length=50)
    can_view = models.BooleanField(default=True)
    can_edit = models.BooleanField(default=True)
    can_search = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.role} - {self.model_name}.{self.field_name}"
    
    
class Bank(AuditModel):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50)
    #logo = models.ImageField(upload_to='bank_logos/', null=True, blank=True)
    contact_person = models.CharField(max_length=255,blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=15,blank=True)
    address = models.TextField(blank=True)

    agreement_start_date = models.DateField()
    agreement_end_date = models.DateField()
    agreement_status = models.CharField(max_length=20, choices=AGREEMENT_STATUS_CHOICES,blank=True)
    agreement_document = models.FileField(upload_to='agreements/', null=True, blank=True)

    products_offered = models.ManyToManyField('LoanProduct', blank=True,related_name="BankProducts")
    max_commission_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    status = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class LoanProduct(AuditModel):
    bank = models.ForeignKey(Bank, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)
    tenure_months = models.IntegerField()
    max_amount = models.DecimalField(max_digits=12, decimal_places=2)
    min_salary_required = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.name} - {self.bank.name}"

class ProductCategory(AuditModel):
    name = models.CharField(max_length=100, unique=True, null=True, blank=True)  # e.g., Loan, Card, Insurance
    description = models.TextField(null=True, blank=True)  
    icon = models.ImageField(upload_to='apsite/category_icons/', null=True, blank=True)
    image = models.ImageField(upload_to='apsite/category_images/', null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Product Category"
        verbose_name_plural = "Product Categories"

    def __str__(self):
        return self.name or "Unnamed Category"

class Product(AuditModel):
    product_category = models.ForeignKey(ProductCategory, on_delete=models.CASCADE, related_name='products', null=True, blank=True)
    name = models.CharField(max_length=100, null=True, blank=True)  # e.g., Personal Loan
    description = models.TextField(null=True, blank=True)  
    features = HTMLField(null=True, blank=True)  # Rich text listing benefits/features
    eligibility_criteria = HTMLField(null=True, blank=True)  # Rich text for eligibility conditions
    product_image = models.ImageField(upload_to='apsite/product_images/', null=True, blank=True)
    product_icon = models.ImageField(upload_to='apsite/product_icons/', null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_index = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Product"
        verbose_name_plural = "Products"

    def __str__(self):
        return self.name or " "
    

class Lead(AuditModel):
#### Personal Details ####
    name = models.CharField(max_length=122,verbose_name="Applicant Name",blank=False)
    father_name = models.CharField(max_length=122, verbose_name="Father's Name",blank=True)
    gender = models.CharField(max_length=5,choices=GENDER_CHOICES,null=True ,blank=True)
    marital_status = models.CharField(max_length=20,choices=MARITAL_STATUS_CHOICES,verbose_name="Marital Status",blank=True)
    dob = models.DateField(null=True,blank=True, verbose_name="Date Of Birth")
    mobile_number = models.CharField(max_length=10,verbose_name="Mobile No",blank=False,validators=[phone_regex])
    alternate_number = models.CharField(max_length=10,verbose_name="Alternate Number",blank=True,validators=[phone_regex])
    email = models.EmailField(blank=True)
    pan = models.CharField(max_length=12,blank=True)
    adhar_number = models.CharField(max_length=12,blank=True)
    present_address = models.CharField(("Present Address"), max_length=200,blank=True)
    permanent_address = models.CharField(("Permanent Address"), max_length=200,blank=True)
    residence_type = models.CharField(max_length=10,choices=RESIDENCE_TYPE_CHOICES,verbose_name="Residence Type",blank=True)
    location = models.CharField(max_length=100,blank=True)
    state = models.CharField("State", max_length=50, choices=INDIAN_STATES, blank=True, null=True)
    pincode = models.CharField(max_length=10,blank=True)

    mother_name = models.CharField(("Mother Name"),max_length=122, blank=True)
    spouse_name = models.CharField(("Spouse Name"),max_length=122, blank=True)
    qualification = models.CharField(max_length=50, choices=QUALIFICATION_CHOICES, blank=True)
    number_of_dependents = models.IntegerField(("No. of Dependent"),blank=True, null=True)
    reference_details_friend = models.TextField(("Reference Details Friend"),blank=True)
    reference_details_relative = models.TextField(("Reference Details Relative"),blank=True)
    nominee_details = models.TextField(("Nominee Details"),blank=True)
    cibil_score = models.PositiveIntegerField(null=True, blank=True, verbose_name="CIBIL Score", help_text="Enter the customer's CIBIL score (e.g., 750)")

#### Occupational Details ####
    company_name = models.CharField(max_length=122, verbose_name="Company Name",blank=True)
    office_address = models.CharField(("Office Address"), max_length=200,blank=True)
    landline_number = models.CharField(("Landline No."), max_length=12,blank=True)
    office_email = models.EmailField(("Office Email Id"),blank=True)
    company_type = models.CharField(("Type Of Company"), max_length=50,choices=COMPANY_TYPE_CHOICES,blank=True)
    company_listing = models.CharField(("Company Listing"), max_length=50,choices=COMPANY_LISTING_CHOICES,blank=True)

    company_category = models.CharField(("Company Category"), max_length=50,choices=COMPANY_CATEGORY_CHOICES,blank=True)
    industry_profession = models.CharField(("Industry Profession"),max_length=100, choices=INDUSTRY_PROFESSION_CHOICES, blank=True)
    mode_of_salary = models.CharField(("Mode Of Salary"),max_length=20, choices=MODE_OF_SALARY_CHOICES, blank=True)
    uan_no = models.CharField(("UAN No."),max_length=20, blank=True)
    department = models.CharField(max_length=50, choices=DEPARTMENT_CHOICES, blank=True)
    work_type = models.CharField(("Work Type"),max_length=50, choices=WORK_TYPE_CHOICES, blank=True)

    employment_type = models.CharField(("Employement Type"),max_length=50, choices=EMPLOYMENT_TYPE_CHOICES, blank=True)
    designation = models.CharField(max_length=100,blank=True)
    doj = models.DateField(("Date Of Joining"),null=True, blank=True)
    current_exp = models.IntegerField(("Current Experience"), blank=True, null=True)
    total_exp = models.IntegerField(("Total Experience"),blank=True, null=True)
    monthly_salary = models.DecimalField(("Net Monthly Salary"),max_digits=10, decimal_places=2,blank=True,null=True)

#### Banking Details ####
    bank = models.ForeignKey(Bank, on_delete=models.CASCADE,blank=True,null=True,verbose_name="Customer Bank")
    account_number = models.CharField("Account No.", max_length=18, validators=[RegexValidator(r'^\d{9,18}$', message="Account number must be 9 to 18 digits.")], null=True, blank=True)
    ifsc_code = models.CharField("IFSC Code", max_length=20, blank=True, null=True)
    description = models.TextField(blank=True)
    date = models.DateTimeField(auto_now_add=True,blank=True)
    dos = models.DateField(default=datetime.date.today,null=True,blank=True)
    sm = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete = models.CASCADE,verbose_name="Sales Manager", related_name="sm_leads",null=True,blank=True)
    team_lead = models.ForeignKey(settings.AUTH_USER_MODEL,verbose_name="Team Leader",
                                  on_delete = models.CASCADE, related_name="team_leads",null=True,blank=True)
#### Loan Detail ####
    require_loan_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    existing_loan_emi = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    tenure = models.IntegerField(null=True, blank=True)
    existing_loan_details = models.TextField(blank=True)
    existing_cc_details = models.TextField(blank=True)
    lender_name = models.ForeignKey(Bank, on_delete=models.CASCADE,blank=True,null=True,verbose_name="Lander Name",related_name="lender_leads")
    process = models.CharField(max_length=10, choices=PROCESS_CHOICES, blank=True)

#### Assignment & Meta ####
    business_head = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Business Head", related_name="business_head_leads", null=True, blank=True)
    business_manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Business Manager", related_name="business_manager_leads", null=True, blank=True)
    sm = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete = models.CASCADE,verbose_name="Sales Manager", related_name="sm_leads",null=True,blank=True)
    team_lead = models.ForeignKey(settings.AUTH_USER_MODEL,verbose_name="Team Leader",
                                  on_delete = models.CASCADE, related_name="team_leads",null=True,blank=True)
    tele_sales_executive = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Tele Sales Executive", related_name="tele_sales_exec_leads", null=True, blank=True)
    backend_executive_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Backend Executive", related_name="backend_exec_leads", null=True, blank=True)

#### Backend Details ####
    product = models.ForeignKey(Product, on_delete=models.CASCADE, blank=True, null=True,verbose_name="Product")
    channel_name = models.CharField(("Channel Name"), max_length=20,choices=CHANNEL_CHOICES,blank=True)
    dol = models.DateField(("Date of Login"), null=True, blank=True)
    login_amount = models.DecimalField(("Login Amount"),max_digits=12, decimal_places=2, null=True, blank=True)
    loan_type = models.CharField(("Loan Type"), max_length=20,choices=LOAN_TYPE_CHOICES,blank=True)
    application_no = models.CharField(("Application No."),max_length=100, blank=True)
    approved_amount = models.DecimalField(("Approved Amount"),max_digits=12, decimal_places=2, null=True, blank=True)
    gross_disbursed = models.DecimalField(("Gross Disbursed"),max_digits=12, decimal_places=2, null=True, blank=True)
    net_disbursed = models.DecimalField(("Net Disbursed"),max_digits=12, decimal_places=2, null=True, blank=True)
    final_remarks = models.TextField(("Final Remarks"),blank=True)
    rate_of_interest = models.DecimalField(("Rate Of Interest"),max_digits=5, decimal_places=2, null=True, blank=True)
    processing_fee = models.DecimalField(("Processing Fee"),max_digits=10, decimal_places=2, null=True, blank=True)
    insurance = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    flexi_fee = models.DecimalField(("Flexi Fee"),max_digits=10, decimal_places=2, null=True, blank=True)
    emi_date = models.DateField(("EMI Date"),null=True, blank=True)
    emi_amount = models.DecimalField(("EMI Amount"),max_digits=10, decimal_places=2, null=True, blank=True)
    subvention = models.CharField(max_length=100, blank=True)
    cashback = models.DecimalField(("Cashback"),max_digits=10, decimal_places=2, null=True, blank=True)
    cpp = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    dod = models.DateField(("Date of Disbursement"), null=True, blank=True)
    backend_executive = models.CharField(("Backend Executive"),max_length=100, blank=True)
    branch_name = models.CharField(("Branch Name"),max_length=100, blank=True)


######## Audit Field ###########
    lead_source = models.CharField(("Lead Source"),max_length=50, choices=LEAD_TYPE_CHOICES, blank=False, null=True)
    status = models.CharField(("Status"),max_length=50, choices=LEAD_STATUS_CHOICES)
    description = models.TextField(blank=True)
    history = HistoricalRecords()
    
    # New field added By Ashutosh
    follow_up_date = models.DateTimeField(("Follow-Up Date"), null=True, blank=True)
    
    ######## Permission ###########
    def clean(self):
        """
        Collect per-field errors and raise a dict so Django attaches messages
        to the respective fields in all contexts (admin, shell, APIs).
        """
        super().clean()

        errors = {}

        # --- EXAMPLE 1: your existing rule (make it field-targeted) ---
        # ---- DATE SEQUENCE VALIDATION ----
        if self.dol and self.dos:
            if self.dol < self.dos:
                errors['dos'] = "Date of Login must be after Date of Source."

        if self.dod and self.dol:
            if self.dod < self.dol:
                errors['dod'] = "Date of Disbursement must be after Date of Login."

        if self.dos and self.dod:
            if self.dod < self.dos: 
                errors['dod'] = "Date of Disbursement must be after Date of Source."

        # --- DoS should not be a future date ---
        if self.dos:
            today = datetime.date.today()
            if self.dos > today:
                errors['dos'] = "Date of Source cannot be a future date. It should be today or earlier."
        
        # ---- STATUS-BASED REQUIRED FIELDS For Bank Porcessing ----
        status_required_fields = [
            'ofb', 'underwriting','disbursed', 'Declined',
            'approved', 'reject_relook', 'approved_hold', 'UW Hold'
        ]       
        if self.status and self.status in status_required_fields:
            # define required field list and corresponding user-friendly names
            readable_status = self.get_status_display()  # ✅ Shortcut method
            required_fields = {
                'channel_name': 'Channel Name',
                'loan_type': 'Loan Type',
                'tenure': 'Tenure',
                'process': 'Process',
                'require_loan_amount': 'Required Loan Amount',
                'login_amount': 'Login Amount',
                'lender_name': 'Lender Name',
                'sm': 'Sales Manager',
                'team_lead': 'Team Leader',
                'tele_sales_executive': 'Tele Sales Executive',
                'business_manager': 'Business Manager',
                'business_head': 'Business Head',
            }

            for field, label in required_fields.items():
                value = getattr(self, field, None)
                # check for blank, None, or empty string
                if value in [None, '']:
                    errors[field] = f"{label} is required when status is {readable_status}."

        # ---- STATUS-BASED: Approved Amount required ----
        if self.status in ['approved', 'approved_hold']:
            if not self.approved_amount:
                errors['approved_amount'] = (
                    f"Approved Amount is required when status is {self.get_status_display()}."
                )

        # ---- STATUS-BASED: Disbursed requires disbursement details ----
        if self.status == 'disbursed':
            readable_status = self.get_status_display()  # e.g., "Disbursed"
            required_fields = {
                'gross_disbursed': 'Gross Disbursed',
                'net_disbursed': 'Net Disbursed',
                'rate_of_interest': 'Rate of Interest',
                'processing_fee': 'Processing Fee',
                'dod': 'Date of Disbursement',
                'dol': 'Date of Login',
                'application_no': 'Application No.',
                
            }
            for field, label in required_fields.items():
                value = getattr(self, field, None)
                if value in [None, '']:
                    errors[field] = f"{label} is required when status is {readable_status}."
        
                    
        # ---- OTHER EXISTING RULES ----
        if self.mobile_number and self.alternate_number:
            if self.mobile_number == self.alternate_number:
                errors['alternate_number'] = "Alternate number must be different from Mobile number."

        if errors:
            raise ValidationError(errors)
        
    class Meta:
        indexes = [

            # Sorting
            models.Index(fields=['-created_date']),
            models.Index(fields=['-modified_at']),

            # Most-used filters
            models.Index(fields=['status']),
            models.Index(fields=['lead_source']),
            models.Index(fields=['loan_type']),
            models.Index(fields=['process']),
            models.Index(fields=['employment_type']),
            models.Index(fields=['channel_name']),

            # Dates
            models.Index(fields=['dos']),
            models.Index(fields=['dol']),
            models.Index(fields=['dod']),
            models.Index(fields=['follow_up_date']),

            # Exact searches
            models.Index(fields=['mobile_number']),
            models.Index(fields=['pan']),
            models.Index(fields=['adhar_number']),
            models.Index(fields=['application_no']),
        ]
        permissions = [
            ("view_lead_history", "Can view lead history"),
        ]
        

           
    def __str__(self):
        return self.name

class LeadFollowUp(AuditModel):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE,null=True,blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE,null=True,blank=True)
    note = models.TextField(null=True,blank=True)
    follow_up_date = models.DateTimeField(null=True,blank=True)
    status = models.CharField(max_length=50, choices=LEAD_STATUS_CHOICES, null=True, blank=True)

    def __str__(self):
        return f"{self.lead.name} - {self.follow_up_date}"


class Document(AuditModel):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE)
    document_type = models.CharField(max_length=100)
    file = models.FileField(upload_to='documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.document_type} - {self.lead.name}"
    
class LoanApplication(AuditModel):
    lead = models.OneToOneField(Lead, on_delete=models.CASCADE)
    product = models.ForeignKey(LoanProduct, on_delete=models.CASCADE)
    loan_amount = models.DecimalField(max_digits=12, decimal_places=2)
    tenure = models.IntegerField(help_text="In months")
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)
    emi = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    status = models.CharField(max_length=50, choices=LEAD_STATUS_CHOICES, default='Submitted to Bank')
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    disbursed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.lead.name} - {self.product.name}"

class BankFeedback(AuditModel):
    application = models.ForeignKey(LoanApplication, on_delete=models.CASCADE)
    feedback = models.TextField()
    status = models.CharField(max_length=50, choices=LEAD_STATUS_CHOICES)
    received_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.application.lead.name} - {self.status}"



class CandidateOnboarding(AuditModel):
    # Candidate Information
    full_name = models.CharField(("Candidate Name"), max_length=100)
    phone = models.CharField(max_length=10,verbose_name="Mobile Number",validators=[phone_regex])
    alternate_number = models.CharField(max_length=10,verbose_name="Alternate Number",blank=True,null=True,validators=[phone_regex])
    email = models.EmailField(("Email ID"),null=True, blank=True,)
    gender = models.CharField(("Gender"), max_length=10, null=True, blank=True,choices=GENDER_CHOICES)
    date_of_birth = models.DateField(("Date of Birth"), null=True, blank=True)
    qualification = models.CharField(("Qualification"), max_length=100, null=True, blank=True,choices=QUALIFICATION_CHOICES)
    experience = models.CharField(("Total Experience (Years)"), max_length=20, null=True, blank=True)
    relevant_exp = models.IntegerField(("Relevant Experience"), blank=True, null=True)
    previous_company = models.CharField(("Previous Company Name"), max_length=100, null=True, blank=True)
    previous_designation = models.CharField(("Previous Designation"), max_length=100, null=True, blank=True)
    current_salary = models.DecimalField(("Current Salary"), max_digits=10, decimal_places=2, null=True, blank=True)
    expected_salary = models.DecimalField(("Expected Salary"), max_digits=10, decimal_places=2, null=True, blank=True)
    candidate_city = models.CharField(("Candidate City"), max_length=100, null=True, blank=True)
    candidate_area = models.CharField(("Candidate Area"), max_length=100, null=True, blank=True)
    industry = models.CharField(("Industry"), max_length=100, choices=INDUSTRY_CHOICES, null=True, blank=True)
    blood_group = models.CharField(("Blood Group"), max_length=5, null=True, blank=True,choices=BLOOD_GROUP_CHOICES)
    birth_place = models.CharField(("Birth Place"), max_length=100, null=True, blank=True)
    father_name = models.CharField(("Father Name"), max_length=100, null=True, blank=True)
    mother_name = models.CharField(("Mother Name"), max_length=100, null=True, blank=True)
    adhar_number = models.CharField(("Adhar Number"), max_length=12, null=True, blank=True)
    photo = models.ImageField("Photo", upload_to="candidate_photos/", null=True, blank=True)
    resume = models.FileField("Resume", upload_to="candidate_resumes/", null=True, blank=True)
    # Interview Details
    source = models.CharField(("Source"), max_length=100, null=False, blank=False,choices=CANDIDATE_SOURCE_CHOICE)
    applied_on = models.DateField(("Applied on"), null=True, blank=True)
    applied_for = models.CharField(("Position Applied For"), max_length=100,choices=CANDIDATE_POSITION_APPLIED_CHOICE)
    #recruiter_name = models.ForeignKey(User,verbose_name=("Recruiter Name"),null=True,blank=True,on_delete=models.SET_NULL,related_name="recruited_candidates")
    recruiter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Recruiter", related_name="recruited_candidates", null=True, blank=True)
    recruiter_feedback = models.TextField(("Recruiter Feedback"), null=True, blank=True)
    calling_date = models.DateField(("Calling Date"), null=True, blank=True)
    candidate_status = models.CharField(("Candidate Status"), max_length=50, choices=CANDIDATE_STATUS_CHOICES, null=False, blank=False)
    interview_date = models.DateField(("Interview Date"), null=True, blank=True)
    #interviewer = models.CharField(("Interviewer"), max_length=100, null=True, blank=True)
    interviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Interviewer", related_name="candidates_interviewer", null=True, blank=True)
    interview_status = models.CharField(("Interview Status"), max_length=50, choices=INTERVIEW_STATUS_CHOICES, null=True, blank=True)
    interview_feedback = models.TextField(("Interview Feedback"), null=True, blank=True)

    # Offer & Joining Details
    #reporting_manager = models.CharField(("Reporting Manager"), max_length=100, null=True, blank=True)
    reporting_manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Reporting Manager", related_name="reporting_manager", null=True, blank=True)
    expected_joining_date = models.DateField(("Expected Joining Date"), null=True, blank=True)
    employee_code = models.CharField(("Employee Code"), max_length=20, null=True, blank=True)
    department = models.CharField(("Department"), max_length=100, null=True, blank=True,choices=CANDIDATE_DEPARTMENT_CHOICE)
    actual_joining_date = models.DateField(("Actual Joining Date"), null=True, blank=True)
    hired_on_salary = models.DecimalField(("Hired On Salary"), max_digits=10, decimal_places=2, null=True, blank=True)
    designation = models.CharField(("Designation"), max_length=100, choices=DESIGNATION_CHOICES, null=True, blank=True)
    training_date = models.DateField(("Training Date"), null=True, blank=True)
    training_status = models.CharField(("Training Status"), max_length=50,choices=CANDIDATE_TRAINING_STATUS_CHOICE, null=True, blank=True)
    training_feedback = models.TextField(("Training Feedback"), null=True, blank=True)

    # Emergency Contact & Address
    current_address = models.TextField(("Current Address"), null=True, blank=True)
    permanent_address = models.TextField(("Permanent Address"), null=True, blank=True)
    emergency_contact_name = models.CharField(("Emergency Contact Name"), max_length=100, null=True, blank=True)
    emergency_contact_number = models.CharField(("Emergency Contact Number"), max_length=15, null=True, blank=True)
    relationship_with_employee = models.CharField(("Relationship with Employee"), max_length=50, null=True, blank=True)
    local_ref_name = models.CharField(("Local Ref Name"), max_length=100, null=True, blank=True)
    local_ref_number = models.CharField(("Local Ref Number"), max_length=15, null=True, blank=True)
    local_ref_relationship = models.CharField(("Local Ref Relationship with Employee"), max_length=100, null=True, blank=True)

    # Employment Status
    employment_status = models.CharField(("Employment Status"), max_length=50, choices=EMPLOYMENT_STATUS_CHOICES, null=True, blank=True)
    resignation_date = models.DateField(("Resignation Date"), null=True, blank=True)
    last_working_day = models.DateField(("Last Working Day"), null=True, blank=True)
    reason_for_resignation = models.CharField(("Reason for Resignation"), max_length=100, choices=REASON_FOR_RESIGNATION_CHOICES, null=True, blank=True)
    remarks = models.TextField(("Remarks / Notes"), null=True, blank=True)

    history = HistoricalRecords()

    def __str__(self):
        return self.full_name

    
    class Meta:
        verbose_name = "Candidate Onboarding"
        verbose_name_plural = "Candidate Onboardings"
        
class GlobalPermissions(models.Model):
    class Meta:
        managed = False  # No DB table
        default_permissions = ()  # Don't add default add/change/delete
        permissions = [
            ("can_export_data", "Can export data across CRM"),
            # Added permission by Ashutosh
            ("can_access_crm", "Can access CRM module"),
            ("can_access_crm_dashboard", "Can access CRM dashboard"),
            ("can_access_hr_module", "Can access HR module"),
            ("can_access_reports", "Can access reports"),
            ("can_edit_default_list_views", "Can edit default list views"),
            ("can_access_bulk_assign", "Can access Bulk Assign"),
            ("can_bypass_ip_restriction","Can Bypass IP Restriction")
        ]

# Product related tables  by Ashutosh
class Contact(AuditModel):
    name = models.CharField(max_length=122, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=12, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    date = models.DateField(null=True, blank=True)
    product_category = models.ForeignKey(ProductCategory, null=True, blank=True, on_delete=models.SET_NULL, related_name='contacts')
    product = models.ForeignKey(Product, null=True, blank=True, on_delete=models.SET_NULL, related_name='contacts')
    def __str__(self):
        return self.name if self.name else "Unnamed Contact"
    
    
    
# Salesforce like list view model by Ashutosh on 5 dec 2025
class ListView(AuditModel):
    app_label = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        default="crm"   
    )
    object_name = models.CharField(max_length=100, null=True, blank=True)
    name = models.CharField(max_length=200, null=True, blank=True)
    visibility = models.CharField(
        max_length=20,
        choices=VISIBILITY_CHOICES,
        null=True,
        blank=True
    )
    visible_groups = models.ManyToManyField("auth.Group", blank=True)
    filter_logic = models.CharField(max_length=200, null=True, blank=True)
    is_default = models.BooleanField(default=False)
    count = models.PositiveIntegerField(null=True, blank=True,default=10,verbose_name="Count")  
    
    def __str__(self):
        return self.name if self.name else f"{self.app_label}.{self.object_name} List View"
    
        
class ListViewField(AuditModel):
    list_view = models.ForeignKey(
        ListView,
        on_delete=models.CASCADE,
        related_name="fields",
        null=True,
        blank=True
    )

    field_name = models.CharField(max_length=255, null=True, blank=True)
    order = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["order"]


class ListViewFilter(AuditModel):

    list_view = models.ForeignKey(
        ListView,
        on_delete=models.CASCADE,
        related_name="filters",
        null=True,
        blank=True
    )

    field_name = models.CharField(max_length=255, null=True, blank=True)
    operator = models.CharField(
        max_length=20,
        choices=OPERATORS,
        null=True,
        blank=True
    )
    value = models.CharField(max_length=255, null=True, blank=True)

    row_number = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["row_number"]


# call LOG 
class CallLog(AuditModel):
    lead = models.ForeignKey("Lead", on_delete=models.CASCADE,null=True, blank=True)

    phone_number = models.CharField(max_length=15,null=True, blank=True)

    call_status = models.CharField(
        max_length=20,
        choices=CALL_LOG_STATUS_CHOICES,
        default="initiated"
    )

    duration = models.IntegerField(null=True, blank=True)  # seconds

    call_time = models.DateTimeField(auto_now_add=True)
    
    call_type = models.CharField(
        max_length=20,
        choices=[
            ("outgoing", "Outgoing"),
            ("incoming", "Incoming"),
            ("missed", "Missed"),
            ("rejected", "Rejected"),
        ],
        null=True,
        blank=True
    )

    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.phone_number} - {self.call_status}"