import os
import pathlib
import re

import ruamel.yaml
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.scanner import RoundTripScanner

from rendercv.exception import RenderCVInternalError, RenderCVUserError


def _load_env_file(env_path: pathlib.Path) -> dict[str, str]:
    """Parse a .env file into a key/value dictionary.

    Why:
        Sensitive fields (email, phone) should not be hard-coded in YAML files
        committed to version control. A .env file next to the YAML lets users
        store private values separately and reference them via ${VAR} syntax.

    Args:
        env_path: Path to the .env file. Silently skipped if it does not exist.

    Returns:
        Dictionary of variable names to their string values.
    """
    env_vars: dict[str, str] = {}
    if not env_path.exists():
        return env_vars
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            env_vars[key] = value
    return env_vars


def _substitute_env_vars(content: str, env_vars: dict[str, str]) -> str:
    """Replace ${VAR} placeholders with values from env_vars or os.environ.

    Why:
        Allows YAML fields like `email: ${EMAIL}` to be resolved at parse time.
        .env file values take precedence; real environment variables serve as
        fallback so CI/CD pipelines can inject values without a .env file.
        Unknown variables are left unchanged so YAML parsing will surface a
        clear validation error rather than silently inserting an empty string.

    Args:
        content: Raw YAML string potentially containing ${VAR} placeholders.
        env_vars: Variables loaded from the .env file.

    Returns:
        YAML string with all resolvable placeholders substituted.
    """

    def replace(match: re.Match) -> str:
        name = match.group(1)
        return env_vars.get(name) or os.environ.get(name, match.group(0))

    return re.sub(r"\$\{([^}]+)\}", replace, content)


def read_yaml(file_path_or_contents: pathlib.Path | str) -> CommentedMap:
    """Parse YAML/JSON content from file path or string.

    Why:
        Validation errors must point to exact YAML locations. CommentedMap
        preserves source coordinates that map Pydantic errors back to input
        lines, enabling user-friendly error tables showing exactly where
        mistakes occur in the input file.

    Example:
        ```py
        data = read_yaml(pathlib.Path("cv.yaml"))
        name = data["cv"]["name"]  # Regular dict access
        # Line info also available: data.lc.data["cv"][0] = (line, col)
        ```

    Args:
        file_path_or_contents: File path or raw YAML string.

    Returns:
        Dictionary with line/column metadata for error reporting.
    """
    if isinstance(file_path_or_contents, pathlib.Path):
        # Check if the file exists:
        if not file_path_or_contents.exists():
            message = f"The input file `{file_path_or_contents}` doesn't exist!"
            raise RenderCVUserError(message)

        # Check the file extension:
        accepted_extensions = [".yaml", ".yml", ".json", ".json5"]
        if file_path_or_contents.suffix not in accepted_extensions:
            message = (
                "The input file should have one of the following extensions:"
                f" {', '.join(accepted_extensions)}. The input file is"
                f" {file_path_or_contents.name}."
            )
            raise RenderCVUserError(message)

        file_content = file_path_or_contents.read_text(encoding="utf-8")
        env_vars = _load_env_file(file_path_or_contents.parent / ".env")
        file_content = _substitute_env_vars(file_content, env_vars)
    else:
        file_content = file_path_or_contents

    yaml_as_dictionary: CommentedMap = yaml.load(file_content)

    if yaml_as_dictionary is None:
        message = "The input file is empty!"
        raise RenderCVUserError(message)

    if isinstance(yaml_as_dictionary, str):
        message = (
            "You probably meant to pass a path to the YAML file, but you passed as a"
            " string and RenderCV interpreted it as the contents of the YAML file."
            f" Pass the path using `pathlib.Path({file_path_or_contents})`."
        )
        raise RenderCVInternalError(message)

    return yaml_as_dictionary


class ScannerNoAlias(RoundTripScanner):
    """Custom Scanner that treats * as a regular character instead of alias syntax.

    Why:
        CV content frequently contains literal * characters (e.g., in Markdown bold
        syntax). Standard YAML interprets * as an alias indicator, causing parse
        errors. This subclass overrides alias handling to treat * as plain text.
    """

    def fetch_alias(self) -> None:
        """Treat * as a plain scalar character instead of alias syntax."""
        self.fetch_plain()


yaml = ruamel.yaml.YAML()
yaml.Scanner = ScannerNoAlias

# Disable ISO date parsing, keep it as a string:
yaml.constructor.yaml_constructors["tag:yaml.org,2002:timestamp"] = (
    lambda loader, node: loader.construct_scalar(node)
)
