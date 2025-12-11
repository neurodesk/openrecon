import subprocess

def executeCommandDirectly(command):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    outputString, _ = process.communicate()
    exitCode = process.wait()
    return exitCode, outputString

def checkRootUserInContainer(dockerImageName):
    """
    Check if the default user in the Docker container is root.
    
    Args:
        dockerImageName: Name/tag of the Docker image to check
    
    Raises:
        Exception: If the user is not root
    """
    print("### Checking user in Docker container...")
    
    # Check the current user in the container
    print("#-> Checking if container runs as root user...")
    exitCode, outputString = executeCommandDirectly([
        "docker", "run", "--rm", "--platform", "linux/amd64",
        dockerImageName,
        "sh", "-c", "id -u"
    ])
    
    if exitCode != 0:
        raise Exception(f"#-> Docker command failed: {outputString}")
    
    # Parse the user ID
    try:
        uid = int(outputString.strip())
        print(f"   ℹ️  Container user ID: {uid}")
        
        if uid != 0:
            # Get username for better error message
            exitCode, usernameOutput = executeCommandDirectly([
                "docker", "run", "--rm", "--platform", "linux/amd64",
                dockerImageName,
                "sh", "-c", "whoami"
            ])
            username = usernameOutput.strip() if exitCode == 0 else "unknown"
            
            raise Exception(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                              ROOT USER ERROR                                 ║
╚══════════════════════════════════════════════════════════════════════════════╝

❌ Container is running as user '{username}' (UID: {uid}) instead of root (UID: 0)

OpenRecon requires the container to run as root user.

Please rebuild your Docker image to run as root user. You may need to:
  • Remove any USER directives that set a non-root user
  • Ensure the base image runs as root

Build stopped.
""")
        
        print(f"   ✓ Container runs as root user ✓\n")
        
    except ValueError as e:
        raise Exception(f"#-> Could not parse user ID from output: {outputString}. Error: {e}")

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Usage: python checkRootUser.py <docker_image_name>")
        sys.exit(1)
    
    dockerImageName = sys.argv[1]
    checkRootUserInContainer(dockerImageName)
