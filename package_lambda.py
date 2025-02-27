import subprocess
import shutil
import os
import sys

def package_lambda():
    # Create a temporary directory for packaging
    if os.path.exists('package'):
        shutil.rmtree('package')
    os.makedirs('package')

    with open('lambda_module/requirements.txt', 'r') as f:
        requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]

    # Install each package individually (more reliable than --platform for all)
    for req in requirements:
        try:
            # First try with platform flag
            subprocess.check_call([
                sys.executable, '-m', 'pip',
                'install',
                req,
                '--platform', 'manylinux2014_x86_64',
                '--target', 'package',
                '--implementation', 'cp',
                '--python-version', '3.11',
                '--only-binary=:all:'
            ], stderr=subprocess.DEVNULL)
            print(f"✅ Installed {req} with platform flag")
        except subprocess.CalledProcessError:
            # If that fails, try normal install
            try:
                subprocess.check_call([
                    sys.executable, '-m', 'pip',
                    'install',
                    req,
                    '--target', 'package'
                ])
                print(f"✅ Installed {req} normally")
            except subprocess.CalledProcessError:
                print(f"⚠️ Failed to install {req}")


    # Copy lambda handler
    shutil.copy('lambda_module/whatsapp_handler.py', 'package/whatsapp_handler.py')
    shutil.copy('lambda_module/multiagent_handler.py', 'package/multiagent_handler.py')

    with open('package/__init__.py', 'w') as f:
        pass
    # Create zip file
    if os.path.exists('lambda_package.zip'):
        os.remove('lambda_package.zip')
    
    shutil.make_archive('lambda_package', 'zip', 'package')

    # Clean up
    shutil.rmtree('package')

if __name__ == '__main__':
    package_lambda()


# import subprocess
# import shutil
# import os
# import sys

# def package_lambda():
#     # Create directories for our handler package and layer
#     if os.path.exists('package'):
#         shutil.rmtree('package')
#     os.makedirs('package')
    
#     if os.path.exists('layer'):
#         shutil.rmtree('layer')
#     os.makedirs('layer/python')
    
#     # Step 1: Install Python dependencies into the layer directory
#     print("Installing dependencies into layer...")
#     subprocess.check_call([
#         sys.executable, '-m', 'pip',
#         'install',
#         '-r', 'lambda_module/requirements.txt',
#         '--target', 'layer/python'
#     ])
    
#     # Step 2: Create the dependency layer ZIP
#     print("Creating dependency layer ZIP...")
#     if os.path.exists('lambda_layer.zip'):
#         os.remove('lambda_layer.zip')
    
#     shutil.make_archive('lambda_layer', 'zip', 'layer')
    
#     # Step 3: Copy just the handler files (without dependencies) to the package dir
#     print("Preparing handler package...")
#     shutil.copy('lambda_module/whatsapp_handler.py', 'package/whatsapp_handler.py')
#     shutil.copy('lambda_module/multiagent_handler.py', 'package/multiagent_handler.py')
    
#     with open('package/__init__.py', 'w') as f:
#         pass
    
#     # Step 4: Create the handler ZIP
#     print("Creating handler package ZIP...")
#     if os.path.exists('lambda_package.zip'):
#         os.remove('lambda_package.zip')
    
#     shutil.make_archive('lambda_package', 'zip', 'package')
    
#     # Clean up
#     shutil.rmtree('package')
#     shutil.rmtree('layer')
    
#     print("\nSUCCESS! Created:")
#     print("- lambda_package.zip (contains your handler code)")
#     print("- lambda_layer.zip (contains your dependencies)")
#     print("\nNow update your CDK stack to use the dependency layer.")

# if __name__ == '__main__':
#     package_lambda()