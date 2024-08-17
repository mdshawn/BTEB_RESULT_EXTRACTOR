import re
import json
import fitz  # PyMuPDF
import os

def ordinal(n):
    """Convert an integer to its ordinal representation."""
    if 10 <= n % 100 <= 20:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return str(n) + suffix

def extract_results(file_path):
    pdf_document = fitz.open(file_path)
    result_data = []
    institute_code = ""
    institute_name = ""
    district = ""
    result_date = None
    semester = None
    regulation = None
    trade = None
    examination_held = None

    # Updated patterns
    institute_pattern = re.compile(r"(\d{5}) - (.*?), (.*?)\n")
    result_date_pattern = re.compile(r"Date\s*:\s*(\d{2}-\d{2}-\d{4})")
    semester_regulation_trade_pattern = re.compile(
        r"(\d{1,2})(?:st|nd|rd|th)\s+Semester\s*\((\d{4}) Regulation\)\s*Examination of (.*?)\s*,"
    )
    examination_held_pattern = re.compile(r"held\s*in\s*(\w+\s*,\s*\d{4})")
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

        # Extracting the result date
        if result_date is None:
            date_match = result_date_pattern.search(text)
            if date_match:
                result_date = date_match.group(1)

        # Extracting semester, regulation, trade, and examination held date
        if semester is None or regulation is None or trade is None or examination_held is None:
            sem_reg_trade_match = semester_regulation_trade_pattern.search(text)
            if sem_reg_trade_match:
                semester = ordinal(int(sem_reg_trade_match.group(1)))
                regulation = sem_reg_trade_match.group(2)
                trade = sem_reg_trade_match.group(3).strip()
            examination_held_match = examination_held_pattern.search(text)
            if examination_held_match:
                examination_held = examination_held_match.group(1).strip()

        # Extracting institute details
        if "Bangladesh Technical Education Board" in text:
            institute_match = institute_pattern.search(text)
            if institute_match:
                institute_code = institute_match.group(1)
                institute_name = institute_match.group(2).strip()
                district = institute_match.group(3).strip()

        for line in lines:
            if collecting_failed_subjects:
                failed_subjects_part = line.strip()
                current_failed_subjects.extend(re.findall(failed_subject_pattern, failed_subjects_part))
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
                        "result_semester": semester,
                        "regulation": regulation,
                        "trade": trade,
                        "examination_held": examination_held
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
                    "result_semester": semester,
                    "regulation": regulation,
                    "trade": trade,
                    "examination_held": examination_held
                })

            failed_start_match = failed_pattern_start.match(line)
            if failed_start_match:
                roll_number = failed_start_match.group(1)
                subjects_str = failed_start_match.group(2).strip()
                current_failed_roll = roll_number
                current_failed_subjects = re.findall(failed_subject_pattern, subjects_str)
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
                        "result_semester": semester,
                        "regulation": regulation,
                        "trade": trade,
                        "examination_held": examination_held
                    })
                    collecting_failed_subjects = False
                    current_failed_roll = None
                    current_failed_subjects = []

            elif collecting_failed_subjects:
                subjects_part_match = failed_pattern_cont.match(line)
                if subjects_part_match:
                    subjects_str = subjects_part_match.group(1).strip()
                    current_failed_subjects.extend(re.findall(failed_subject_pattern, subjects_str))
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
                        "result_semester": semester,
                        "regulation": regulation,
                        "trade": trade,
                        "examination_held": examination_held
                    })
                    collecting_failed_subjects = False
                    current_failed_roll = None
                    current_failed_subjects = []

    return result_data

def save_to_json(data, output_path):
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def process_directory(input_dir, output_dir):
    # Create the output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Process each PDF file in the input directory
    for filename in os.listdir(input_dir):
        if filename.lower().endswith('.pdf'):
            file_path = os.path.join(input_dir, filename)
            results = extract_results(file_path)
            
            # Determine the semester if there are more than 50 null values
            non_null_semesters = [result["result_semester"] for result in results if result["result_semester"] is not None]
            if len(non_null_semesters) > 0:
                # Use the most common non-null semester if available
                from collections import Counter
                common_semester = Counter(non_null_semesters).most_common(1)
                if common_semester:
                    common_semester = common_semester[0][0]
                    for result in results:
                        if result["result_semester"] is None:
                            result["result_semester"] = common_semester
            else:
                # Check if more than 50 `result_semester` values are null
                null_semesters_count = sum(1 for result in results if result["result_semester"] is None)
                if null_semesters_count > 50:
                    print(f"\nThe following file(s) need a result semester input: {filename}")
                    result_semester = input(f"Enter result semester for file {filename}: ")
                    for result in results:
                        if result["result_semester"] is None:
                            result["result_semester"] = result_semester

            # Generate output file name based on input PDF file name
            output_json_path = os.path.join(output_dir, os.path.splitext(filename)[0] + ".json")
            
            save_to_json(results, output_json_path)
            print(f"Results extracted to {output_json_path}")

# Main execution
if __name__ == "__main__":
    input_directory = input("Enter the path of the input directory: ")  # User inputs the directory containing PDF files
    output_directory = os.path.join(input_directory, "output")  # Define output directory
    
    process_directory(input_directory, output_directory)
