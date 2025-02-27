import subprocess
import shutil
import os

def package_lambda():
    # Create a temporary directory for packaging
    if os.path.exists('package'):
        shutil.rmtree('package')
    os.makedirs('package')

    # Install requirements
    subprocess.check_call([
        'pip',
        'install',
        '-r',
        'lambda_module/requirements.txt',
        '--target',
        'package'
    ])

    # Copy lambda handler
    shutil.copy('lambda_module/whatsapp_handler.py', 'package/whatsapp_handler.py')

    # Create zip file
    if os.path.exists('lambda_package.zip'):
        os.remove('lambda_package.zip')
    
    shutil.make_archive('lambda_package', 'zip', 'package')

    # Clean up
    shutil.rmtree('package')

if __name__ == '__main__':
    package_lambda()