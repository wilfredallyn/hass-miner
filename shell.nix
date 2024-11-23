{ pkgs ? import <nixpkgs> {
    config = {};
    overlays = [];
    extraNixpkgsArgs.config.allowUnfree = true;
    nixConfig.extra-experimental-features = [ "nix-command" "flakes" ];
  }
}:

pkgs.mkShell {
  buildInputs = with pkgs; [
    black
    poetry
    python3
    python3Packages.pip
    python3Packages.pydantic
    python3.pkgs.virtualenv
    python3.pkgs.jupyter
    python3.pkgs.jupyterlab
    python3.pkgs.ipykernel
  ];

  shellHook = ''
    export PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring
    # Create venv if it doesn't exist
    if [ ! -d "venv" ]; then
      python -m venv venv
    fi
    source venv/bin/activate

    # install local pyasic
    export PYTHONPATH=$PWD:$PWD/../pyasic:$PYTHONPATH
    # add with pyproject.toml pip install -e .

    # Install pyasic dependencies using poetry
    cd ../pyasic
    poetry install --no-root
    cd -

    # pip install pyasic
    pip install nest-asyncio

    # Install and register the kernel
    pip install ipykernel
    python -m ipykernel install --user --name=venv --display-name="Python (venv)"
  '';
}
