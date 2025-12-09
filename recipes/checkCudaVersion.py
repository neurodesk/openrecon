import subprocess
from packaging import version

def executeCommandDirectly(command):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    outputString, _ = process.communicate()
    exitCode = process.wait()
    return exitCode, outputString

def checkCudaVersionInContainer(dockerImageName, maxCudaVersion="11.8"):
    """
    Check CUDA version inside a Docker container.
    Checks both nvcc (CUDA toolkit) and PyTorch CUDA version.
    
    Args:
        dockerImageName: Name/tag of the Docker image to check
        maxCudaVersion: Maximum allowed CUDA version (inclusive)
    
    Raises:
        Exception: If CUDA version is greater than maxCudaVersion or if check fails
    """
    print("### Checking CUDA version in Docker container...")
    
    cuda_versions_found = []
    
    # Check 1: nvcc version (CUDA toolkit)
    print("#-> Checking CUDA toolkit (nvcc)...")
    exitCode, outputString = executeCommandDirectly([
        "docker", "run", "--rm", "--platform", "linux/amd64",
        dockerImageName,
        "sh", "-c", "nvcc --version 2>/dev/null || echo 'CUDA_NOT_FOUND'"
    ])
    
    if exitCode != 0:
        raise Exception(f"#-> Docker command failed: {outputString}")
    
    if "CUDA_NOT_FOUND" not in outputString:
        # Parse CUDA version from nvcc output
        # Output format: "Cuda compilation tools, release 11.8, V11.8.89"
        try:
            for line in outputString.split('\n'):
                if 'release' in line.lower():
                    # Extract version number after "release"
                    parts = line.split('release')
                    if len(parts) > 1:
                        version_str = parts[1].split(',')[0].strip()
                        cuda_versions_found.append(('CUDA Toolkit (nvcc)', version_str))
                        print(f"   ✓ CUDA Toolkit version: {version_str}")
                        break
        except Exception as e:
            print(f"   ⚠️  Could not parse nvcc version: {e}")
    else:
        print("   ℹ️  CUDA toolkit (nvcc) not found")
    
    # Check 2: PyTorch CUDA version
    print("#-> Checking PyTorch CUDA version...")
    exitCode, outputString = executeCommandDirectly([
        "docker", "run", "--rm", "--platform", "linux/amd64",
        dockerImageName,
        "sh", "-c", "python3 -c 'import torch; print(torch.version.cuda)' 2>/dev/null || echo 'TORCH_NOT_FOUND'"
    ])
    
    if exitCode != 0:
        raise Exception(f"#-> Docker command failed: {outputString}")
    
    if "TORCH_NOT_FOUND" not in outputString and outputString.strip():
        torch_cuda_version = outputString.strip()
        if torch_cuda_version and torch_cuda_version != "None":
            cuda_versions_found.append(('PyTorch CUDA', torch_cuda_version))
            print(f"   ✓ PyTorch CUDA version: {torch_cuda_version}")
    else:
        print("   ℹ️  PyTorch not found or no CUDA support")
    
    # If no CUDA found at all, skip the check
    if not cuda_versions_found:
        print("#-> No CUDA installation found in container")
        print("#-> Skipping CUDA version check\n")
        return
    
    # Validate all found CUDA versions
    print("#-> Validating CUDA versions...")
    for cuda_type, parsedCudaVersion in cuda_versions_found:
        try:
            if version.parse(parsedCudaVersion) > version.parse(maxCudaVersion):
                raise Exception(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                              CUDA VERSION ERROR                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

❌ {cuda_type} version {parsedCudaVersion} found in container exceeds maximum allowed version {maxCudaVersion}

OpenRecon requires CUDA version ≤ {maxCudaVersion}

Please rebuild your Docker image with CUDA {maxCudaVersion} or lower.

Build stopped.
""")
            print(f"   ✓ {cuda_type} {parsedCudaVersion} is valid (≤ {maxCudaVersion})")
        except version.InvalidVersion as e:
            raise Exception(f"#-> Invalid CUDA version format for {cuda_type}: {parsedCudaVersion}. Error: {e}")
    
    print(f"#-> All CUDA versions are valid ✓\n")

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Usage: python checkCudaVersion.py <docker_image_name> [max_cuda_version]")
        sys.exit(1)
    
    dockerImageName = sys.argv[1]
    maxCudaVersion = sys.argv[2] if len(sys.argv) > 2 else "11.8"
    
    checkCudaVersionInContainer(dockerImageName, maxCudaVersion)
