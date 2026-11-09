"""
Menshen: custom django-configurations values.

Adapted from django-lasuite's `configuration.values` module (MIT license):
https://github.com/suitenumerique/django-lasuite
"""

import os
from pathlib import Path

from configurations import values


class SecretFileValue(values.Value):
    """
    Value read from an environment variable, or from a file referenced by one.

    The value set is either (in order of priority):
    * The content of the file referenced by the `{name}_{file_suffix}` environment variable.
    * The value of the `{name}` environment variable.
    * The default value.
    """

    file_suffix = "FILE"

    def __init__(self, *args, **kwargs):
        """Initialize the value."""
        self.file_suffix = kwargs.pop("file_suffix", self.file_suffix)
        super().__init__(*args, **kwargs)

    def setup(self, name):
        """Get the value from environment variables."""
        value = self.default
        if self.environ:
            full_environ_name = self.full_environ_name(name)
            full_environ_name_file = f"{full_environ_name}_{self.file_suffix}"
            if full_environ_name_file in os.environ:
                path = Path(os.environ[full_environ_name_file])
                if not path.exists():
                    raise ValueError(f"Path {str(path)!r} does not exist.")
                try:
                    value = self.to_python(path.read_text().removesuffix("\n"))
                except OSError as err:
                    raise ValueError(f"Path {str(path)!r} cannot be read: {err!r}") from err
            elif full_environ_name in os.environ:
                value = self.to_python(os.environ[full_environ_name])
            elif self.environ_required:
                raise ValueError(
                    f"Value {name!r} is required to be set as the environment variable "
                    f"{full_environ_name_file!r} or {full_environ_name!r}"
                )
        self.value = value
        return value
