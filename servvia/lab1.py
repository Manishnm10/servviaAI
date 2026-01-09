from fpdf import FPDF
import datetime

class PDFReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'CITY GENERAL HOSPITAL - LABORATORY SERVICES', 0, 1, 'C')
        self.set_font('Arial', 'I', 10)
        self.cell(0, 10, '123 Medical Center Dr, Bengaluru, KA, 560001 | Phone: (080) 555-0199', 0, 1, 'C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def create_hematology_report():
    pdf = PDFReport()
    pdf.add_page()
    
    # Patient Info
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "HEMATOLOGY REPORT (CBC)", 0, 1, 'L')
    pdf.set_font("Arial", "", 10)
    pdf.multi_cell(0, 6, "Patient: Doe, John A.\nID: 123456789\nDOB: 05/14/1978\nGender: Male\nDate: 10/25/2023")
    pdf.ln(5)
    
    # Table Header
    pdf.set_fill_color(200, 220, 255)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(50, 10, "Test Name", 1, 0, 'L', 1)
    pdf.cell(30, 10, "Result", 1, 0, 'L', 1)
    pdf.cell(30, 10, "Units", 1, 0, 'L', 1)
    pdf.cell(40, 10, "Ref Range", 1, 0, 'L', 1)
    pdf.cell(30, 10, "Flag", 1, 1, 'L', 1)
    
    # Data
    data = [
        ("WBC Count", "7.5", "x10^3/uL", "4.5 - 11.0", ""),
        ("RBC Count", "4.95", "x10^6/uL", "4.50 - 5.90", ""),
        ("Hemoglobin", "12.8", "g/dL", "13.5 - 17.5", "LOW"),
        ("Hematocrit", "39.2", "%", "41.0 - 53.0", "LOW"),
        ("MCV", "79.2", "fL", "80.0 - 100.0", "LOW"),
        ("Platelet Count", "255", "x10^3/uL", "150 - 450", "")
    ]
    
    pdf.set_font("Arial", "", 10)
    for row in data:
        pdf.cell(50, 10, row[0], 1)
        
        # Bold abnormal results
        if row[4] != "":
            pdf.set_font("Arial", "B", 10)
        else:
            pdf.set_font("Arial", "", 10)
            
        pdf.cell(30, 10, row[1], 1)
        pdf.set_font("Arial", "", 10) # Reset
        pdf.cell(30, 10, row[2], 1)
        pdf.cell(40, 10, row[3], 1)
        
        # Color the Flag
        if row[4] != "":
            pdf.set_text_color(255, 0, 0)
        pdf.cell(30, 10, row[4], 1, 1)
        pdf.set_text_color(0, 0, 0)

    pdf.ln(10)
    pdf.multi_cell(0, 6, "Comments: Peripheral blood smear review confirms findings. Mild microcytic anemia present.")
    
    pdf.output("report_1_hematology.pdf")
    print("Generated: report_1_hematology.pdf")

def create_chemistry_report():
    pdf = PDFReport()
    pdf.add_page()
    
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "CHEMISTRY REPORT (BMP)", 0, 1, 'L')
    pdf.set_font("Arial", "", 10)
    pdf.multi_cell(0, 6, "Patient: Smith, Jane E.\nID: 987654321\nDOB: 11/22/1962\nGender: Female\nDate: 10/25/2023")
    pdf.ln(5)
    
    # Table Header
    pdf.set_fill_color(200, 220, 255)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(50, 10, "Test Name", 1, 0, 'L', 1)
    pdf.cell(30, 10, "Result", 1, 0, 'L', 1)
    pdf.cell(30, 10, "Units", 1, 0, 'L', 1)
    pdf.cell(40, 10, "Ref Range", 1, 0, 'L', 1)
    pdf.cell(30, 10, "Flag", 1, 1, 'L', 1)
    
    data = [
        ("Glucose", "165", "mg/dL", "70 - 99", "HIGH"),
        ("BUN", "18", "mg/dL", "7 - 20", ""),
        ("Creatinine", "0.95", "mg/dL", "0.60 - 1.10", ""),
        ("Sodium", "140", "mmol/L", "136 - 145", ""),
        ("Potassium", "4.2", "mmol/L", "3.5 - 5.1", ""),
    ]
    
    pdf.set_font("Arial", "", 10)
    for row in data:
        pdf.cell(50, 10, row[0], 1)
        if row[4] != "":
            pdf.set_font("Arial", "B", 10)
        else:
            pdf.set_font("Arial", "", 10)
        pdf.cell(30, 10, row[1], 1)
        pdf.set_font("Arial", "", 10)
        pdf.cell(30, 10, row[2], 1)
        pdf.cell(40, 10, row[3], 1)
        if row[4] != "":
            pdf.set_text_color(255, 0, 0)
        pdf.cell(30, 10, row[4], 1, 1)
        pdf.set_text_color(0, 0, 0)

    pdf.output("report_2_chemistry.pdf")
    print("Generated: report_2_chemistry.pdf")

def create_microbiology_report():
    pdf = PDFReport()
    pdf.add_page()
    
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "MICROBIOLOGY REPORT (Urine Culture)", 0, 1, 'L')
    pdf.set_font("Arial", "", 10)
    pdf.multi_cell(0, 6, "Patient: Jones, Robert T.\nID: 555123456\nDOB: 02/10/1990\nDate: 10/24/2023")
    pdf.ln(5)
    
    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 10, "Culture Result:", 0, 1)
    pdf.set_font("Arial", "", 10)
    pdf.multi_cell(0, 6, "> 100,000 CFU/mL Escherichia coli")
    pdf.ln(5)

    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 10, "Susceptibility:", 0, 1)
    
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(80, 10, "Antibiotic", 1, 0, 'L', 1)
    pdf.cell(40, 10, "Interpretation", 1, 0, 'L', 1)
    pdf.cell(30, 10, "MIC", 1, 1, 'L', 1)
    
    data = [
        ("Ampicillin", "Resistant", ">= 32"),
        ("Cefazolin", "Sensitive", "<= 2"),
        ("Ciprofloxacin", "Sensitive", "<= 0.25"),
        ("Nitrofurantoin", "Sensitive", "<= 32"),
        ("Trimethoprim/Sulfa", "Resistant", ">= 4/76")
    ]
    
    pdf.set_font("Arial", "", 10)
    for row in data:
        pdf.cell(80, 10, row[0], 1)
        if row[1] == "Resistant":
            pdf.set_text_color(255, 0, 0)
            pdf.set_font("Arial", "B", 10)
        else:
            pdf.set_text_color(0, 100, 0)
            pdf.set_font("Arial", "", 10)
        pdf.cell(40, 10, row[1], 1)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Arial", "", 10)
        pdf.cell(30, 10, row[2], 1, 1)

    pdf.output("report_3_microbiology.pdf")
    print("Generated: report_3_microbiology.pdf")

def create_pathology_report():
    pdf = PDFReport()
    pdf.add_page()
    
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "SURGICAL PATHOLOGY REPORT", 0, 1, 'L')
    pdf.set_font("Arial", "", 10)
    pdf.multi_cell(0, 6, "Patient: White, Emily R.\nID: 777888999\nSpecimen: Skin biopsy, right forearm\nDate: 10/23/2023")
    pdf.ln(5)
    
    sections = [
        ("Pre-Operative Diagnosis", "Lesion, right forearm, rule out malignancy."),
        ("Gross Description", "Received in formalin is a skin ellipse measuring 1.2 x 0.8 x 0.4 cm. The epidermal surface shows a central 0.5 cm tan-pink area."),
        ("Microscopic Description", "Sections show an invasive neoplasm composed of basaloid cells arranged in islands and nests originating from the epidermis. Peripheral palisading of nuclei is present."),
        ("Final Diagnosis", "SKIN, RIGHT FOREARM, BIOPSY:\nBasal Cell Carcinoma, nodular type.")
    ]
    
    for title, content in sections:
        pdf.set_font("Arial", "B", 10)
        pdf.cell(0, 10, title + ":", 0, 1)
        pdf.set_font("Arial", "", 10)
        pdf.multi_cell(0, 6, content)
        pdf.ln(3)

    pdf.ln(10)
    pdf.set_font("Arial", "I", 10)
    pdf.cell(0, 10, "Electronically signed by Dr. A. Gupta, MD", 0, 1)

    pdf.output("report_4_pathology.pdf")
    print("Generated: report_4_pathology.pdf")

if __name__ == "__main__":
    create_hematology_report()
    create_chemistry_report()
    create_microbiology_report()
    create_pathology_report()