import json
import os

EXTENSIONS_DIR = 'extensions'

def fix_package_json(filepath):
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Skipping {filepath}: {e}")
        return False

    changed = False

    # 1. Ensure autocrab is not in dependencies
    if 'dependencies' in data and 'autocrab' in data['dependencies']:
        print(f"Removing autocrab from dependencies in {filepath}")
        del data['dependencies']['autocrab']
        changed = True
        # If dependencies is empty, maybe remove it? Or leave it.

    # 2. Add autocrab to devDependencies as workspace:*
    dev_deps = data.get('devDependencies', {})
    if 'autocrab' not in dev_deps or dev_deps['autocrab'] != 'workspace:*':
        print(f"Adding autocrab: workspace:* to devDependencies in {filepath}")
        dev_deps['autocrab'] = 'workspace:*'
        data['devDependencies'] = dev_deps
        changed = True

    # 3. Ensure peerDependencies has autocrab if it's not present (optional, but good practice if it's a plugin)
    # Actually, let's respect the existing structure. If it had openclaw before, rename script should have handled it.
    # But if it didn't have it, we shouldn't force add peerDep unless we know it needs it.
    # The error "direct dependency" suggests pnpm is trying to resolve it because it's required somewhere (maybe transitively or implicitly).
    # But for now, let's just make sure devDeps has it for local linking.

    if changed:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
            # Add newline at EOF
            f.write('\n')
        return True
    return False

def main():
    root_dir = os.getcwd()
    extensions_path = os.path.join(root_dir, EXTENSIONS_DIR)
    
    if not os.path.exists(extensions_path):
        print(f"Extensions directory not found: {extensions_path}")
        return

    for item in os.listdir(extensions_path):
        item_path = os.path.join(extensions_path, item)
        if os.path.isdir(item_path):
            pkg_json_path = os.path.join(item_path, 'package.json')
            if os.path.exists(pkg_json_path):
                fix_package_json(pkg_json_path)

if __name__ == '__main__':
    main()
