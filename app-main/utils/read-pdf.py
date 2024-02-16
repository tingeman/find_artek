import  PyPDF4

# 


# Function to read and extract text from a PDF file
def read_pdf(file_path):
    # Open the PDF file
    with open(file_path, 'rb') as file:
        # Create a PDF reader object
        pdf_reader =  PyPDF4.PdfFileReader(file)
        # Initialize a variable to store extracted text
        text_content = ''
        # Loop through each page in the PDF
        for page_num in range(pdf_reader.numPages):
            # Get a specific page
            page = pdf_reader.getPage(page_num)
            # Extract text from the page
            text_content += page.extractText()
    return text_content





def run():
    pdf_content = read_pdf('/usr/src/project/shared-project-data/find_artek_static/media/reports/14-14.pdf')
    
    print(pdf_content)

if __name__ == '__main__':
    run()