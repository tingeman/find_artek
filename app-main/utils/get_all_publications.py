import os
import glob

def get_all_publications():
    base_path = "/usr/src/project/shared-project-data/find_artek_static/media/reports"
    years = os.listdir(base_path)  # List all directories (years) in the base path

    reports = []
    for year in years:
        year_path = os.path.join(base_path, year)
        if os.path.isdir(year_path):  # Check if it's a directory
            for report_file in os.listdir(year_path):
                if report_file.endswith('.pdf'):  # Check if the file is a PDF
                    report_id = os.path.splitext(report_file)[0]
                    full_path = os.path.join(year_path, report_file)
                    reports.append((report_id, full_path))
    
    return reports

def run():
    # You can implement whatever you want to do with the reports here
    pass

if __name__ == '__main__':
    reports = get_all_publications()
    # You can do something with the reports here, like printing them
    print(reports)