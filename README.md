# my-package

Here is a quick tutorial on how to locally install the package.

## How to install `my-package` locally

`cd` into the project directory:

```bash
cd my-package
```

Create and activate a new conda environment:

```bash
conda create -n my-package_env python=<max_python_version>
conda activate my-package_env
```

### Method 1: Install your package with dependencies sourced from pip

It's simple. The only command required is the following:

```bash
conda install --file requirements/conda.txt
conda install --file requirements/pip.txt
pip install -e .
```

> The above command will automatically install the dependencies listed in `requirements/pip.txt`.

### Method 2: Install your package with dependencies sourced from pip/conda 

Not available for now.

## Verify your package has been installed

Verify the installation:

```bash
pip list
```

Great! The package is now importable in any Python scripts located on your local machine. For more information, please refer to the Level 4 documentation at [https://billingegroup.github.io/scikit-package/](https://billingegroup.github.io/scikit-package/).
