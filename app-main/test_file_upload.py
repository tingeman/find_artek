#!/usr/bin/env python3
"""
Test script to verify the file upload functionality works correctly.
This tests the hybrid approach with temporary file storage.
"""

import os
import sys
import django
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User
import tempfile

# Setup Django
sys.path.append('/workspace/app-main')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'find_artek.development_settings')
django.setup()

from publications.models import Publication, FileObject, PubType
from publications.utils import handle_publication_file_upload


def test_file_upload():
    """Test the file upload functionality with temp storage"""
    
    print("🧪 Testing file upload functionality...")
    
    # Create a test user if needed
    user, created = User.objects.get_or_create(
        username='test_user', 
        defaults={'email': 'test@example.com'}
    )
    print(f"📝 Using test user: {user.username}")
    
    # Get or create a publication type
    pub_type, created = PubType.objects.get_or_create(
        name='Report',
        defaults={'bibtex_type_name': 'techreport'}
    )
    print(f"📄 Using publication type: {pub_type.name}")
    
    # Create a temporary publication for testing
    temp_pub = Publication()
    temp_pub.title = f"temp_{int(__import__('time').time())}_test_upload"
    temp_pub.type = pub_type
    temp_pub.created_by = user
    temp_pub.modified_by = user
    temp_pub.save()
    print(f"📁 Created temporary publication: {temp_pub.title}")
    
    # Create a test PDF file
    test_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\nxref\n0 4\n0000000000 65535 f \n0000000010 00000 n \n0000000060 00000 n \n0000000120 00000 n \ntrailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n180\n%%EOF"
    uploaded_file = SimpleUploadedFile(
        "test_report.pdf", 
        test_content, 
        content_type="application/pdf"
    )
    print(f"📎 Created test PDF file: {uploaded_file.name} ({len(test_content)} bytes)")
    
    # Test temporary file storage
    print("\n1️⃣ Testing temporary file storage...")
    file_obj = handle_publication_file_upload(temp_pub, uploaded_file, temp_storage=True)
    print(f"✅ Temp file created: {file_obj.file.name}")
    print(f"🏠 File location: {file_obj.file.path}")
    
    # Verify the file exists
    if os.path.exists(file_obj.file.path):
        print(f"✅ File exists on filesystem")
        print(f"📏 File size: {os.path.getsize(file_obj.file.path)} bytes")
    else:
        print(f"❌ File does not exist on filesystem!")
        return False
    
    # Test moving file to final location
    print("\n2️⃣ Testing file move to final location...")
    
    # Create a final publication
    final_pub = Publication()
    final_pub.title = "Final Test Publication"
    final_pub.number = "TEST001"
    final_pub.year = 2024
    final_pub.type = pub_type
    final_pub.created_by = user
    final_pub.modified_by = user
    final_pub.save()
    print(f"📁 Created final publication: {final_pub.title}")
    
    # Test normal file storage
    uploaded_file.seek(0)  # Reset file pointer
    final_file_obj = handle_publication_file_upload(final_pub, uploaded_file, temp_storage=False)
    print(f"✅ Final file created: {final_file_obj.file.name}")
    print(f"🏠 File location: {final_file_obj.file.path}")
    
    # Verify the final file exists
    if os.path.exists(final_file_obj.file.path):
        print(f"✅ Final file exists on filesystem")
        print(f"📏 File size: {os.path.getsize(final_file_obj.file.path)} bytes")
    else:
        print(f"❌ Final file does not exist on filesystem!")
        return False
    
    # Test cleanup command
    print("\n3️⃣ Testing cleanup functionality...")
    from django.core.management import call_command
    from io import StringIO
    
    out = StringIO()
    call_command('cleanup_temp_files', '--dry-run', stdout=out)
    output = out.getvalue()
    print(f"🧹 Cleanup command output:\n{output}")
    
    # Cleanup test data
    print("\n🧽 Cleaning up test data...")
    temp_pub.delete()
    final_pub.delete()
    file_obj.delete()
    final_file_obj.delete()
    
    # Try to remove the test files
    try:
        if os.path.exists(file_obj.file.path):
            os.remove(file_obj.file.path)
            print("🗑️ Removed temp test file")
    except:
        pass
    
    try:
        if os.path.exists(final_file_obj.file.path):
            os.remove(final_file_obj.file.path)
            print("🗑️ Removed final test file")
    except:
        pass
    
    print("\n🎉 Test completed successfully!")
    return True


if __name__ == '__main__':
    try:
        success = test_file_upload()
        if success:
            print("\n✅ All tests passed!")
            sys.exit(0)
        else:
            print("\n❌ Some tests failed!")
            sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
