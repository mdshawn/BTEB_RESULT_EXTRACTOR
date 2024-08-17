import re
import json
import fitz  # PyMuPDF
import os

def extract_results(file_path, semester):
    pdf_document = fitz.open(file_path)
    result_data = []
    institute_code = ""
    institute_name = ""
    district = ""
    result_date = None

    institute_pattern = re.compile(r"(\d{5}) - (.*?), (.*?)\n")
    result_date_pattern = re.compile(r"Date : (\d{2}-\d{2}-\d{4})")
    passed_pattern = re.compile(r"(\d{6}) \(\s*([\d.]+)\s*\)")
    failed_pattern_start = re.compile(r"(\d{6}) \{(.*?)$")
    failed_pattern_cont = re.compile(r"^(.*?)\}")
    failed_subject_pattern = re.compile(r"(\d{5,6})\((T|P)\)")

    collecting_failed_subjects = False
    current_failed_roll = None
    current_failed_subjects = []

    for page_num in range(pdf_document.page_count):
        page = pdf_document.load_page(page_num)
        text = page.get_text("text")
        lines = text.split('\n')

        if result_date is None:
            for line in lines[:10]:  # Check the first 10 lines for the date
                date_match = result_date_pattern.search(line)
                if date_match:
                    result_date = date_match.group(1)
                    break

        if "Bangladesh Technical Education Board" in text:
            institute_match = institute_pattern.search(text)
            if institute_match:
                institute_code = institute_match.group(1)
                institute_name = institute_match.group(2).strip()
                district = institute_match.group(3).strip()

        for line in lines:
            if collecting_failed_subjects:
                failed_subjects_part = line.strip()
                current_failed_subjects.extend(re.findall(r"(\d{5,6})\((T|P)\)", failed_subjects_part))
                if "}" in line:
                    result_data.append({
                        "roll_number": current_failed_roll,
                        "result": {
                            "status": "failed",
                            "failed_subjects": [{"subject_code": sub[0], "status": sub[1]} for sub in current_failed_subjects]
                        },
                        "institute_code": institute_code,
                        "institute_name": institute_name,
                        "district": district,
                        "result_date": result_date,
                        "result_semester": semester
                    })
                    collecting_failed_subjects = False
                    current_failed_roll = None
                    current_failed_subjects = []
                continue

            passed_matches = passed_pattern.findall(line)
            for match in passed_matches:
                roll_number = match[0]
                gpa = float(match[1])
                result_data.append({
                    "roll_number": roll_number,
                    "result": {
                        "status": "passed",
                        "GPA": gpa
                    },
                    "institute_code": institute_code,
                    "institute_name": institute_name,
                    "district": district,
                    "result_date": result_date,
                    "result_semester": semester
                })

            failed_start_match = failed_pattern_start.match(line)
            if failed_start_match:
                roll_number = failed_start_match.group(1)
                subjects_str = failed_start_match.group(2).strip()
                current_failed_roll = roll_number
                current_failed_subjects = re.findall(r"(\d{5,6})\((T|P)\)", subjects_str)
                if "}" not in line:
                    collecting_failed_subjects = True
                else:
                    result_data.append({
                        "roll_number": roll_number,
                        "result": {
                            "status": "failed",
                            "failed_subjects": [{"subject_code": sub[0], "status": sub[1]} for sub in current_failed_subjects]
                        },
                        "institute_code": institute_code,
                        "institute_name": institute_name,
                        "district": district,
                        "result_date": result_date,
                        "result_semester": semester
                    })
                    collecting_failed_subjects = False
                    current_failed_roll = None
                    current_failed_subjects = []

            elif collecting_failed_subjects:
                subjects_part_match = failed_pattern_cont.match(line)
                if subjects_part_match:
                    subjects_str = subjects_part_match.group(1).strip()
                    current_failed_subjects.extend(re.findall(r"(\d{5,6})\((T|P)\)", subjects_str))
                    result_data.append({
                        "roll_number": current_failed_roll,
                        "result": {
                            "status": "failed",
                            "failed_subjects": [{"subject_code": sub[0], "status": sub[1]} for sub in current_failed_subjects]
                        },
                        "institute_code": institute_code,
                        "institute_name": institute_name,
                        "district": district,
                        "result_date": result_date,
                        "result_semester": semester
                    })
                    collecting_failed_subjects = False
                    current_failed_roll = None
                    current_failed_subjects = []

    return result_data

def save_to_json(data, output_path):
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# Main execution
if __name__ == "__main__":
    pdf_path = input("Enter the path of the PDF file: ")  # User inputs the PDF file path
    semester = input("Enter the semester: ")  # User inputs the semester

    # Generate output file name based on input PDF file name
    base_name = os.path.basename(pdf_path)
    output_json_path = os.path.splitext(base_name)[0] + ".json"

    results = extract_results(pdf_path, semester)
    save_to_json(results, output_json_path)

    print(f"Results extracted to {output_json_path}")
