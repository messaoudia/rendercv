import functools
import re
from typing import Literal, get_args

import pydantic
import pydantic_core
import pydantic_extra_types.phone_numbers as pydantic_phone_numbers
from pydantic.json_schema import SkipJsonSchema

from ...pydantic_error_handling import CustomPydanticErrorTypes
from ..base import BaseModelWithoutExtraKeys

url_validator = pydantic.TypeAdapter[pydantic.HttpUrl](pydantic.HttpUrl)


type SocialNetworkName = Literal[
    "LinkedIn",
    "GitHub",
    "GitLab",
    "IMDB",
    "Instagram",
    "ORCID",
    "Mastodon",
    "StackOverflow",
    "ResearchGate",
    "YouTube",
    "Google Scholar",
    "Telegram",
    "WhatsApp",
    "Leetcode",
    "X",
    "Bluesky",
    "Reddit",
]
available_social_networks = get_args(SocialNetworkName.__value__)
url_dictionary: dict[SocialNetworkName, str] = {
    "LinkedIn": "https://linkedin.com/in/",
    "GitHub": "https://github.com/",
    "GitLab": "https://gitlab.com/",
    "IMDB": "https://imdb.com/name/",
    "Instagram": "https://instagram.com/",
    "ORCID": "https://orcid.org/",
    "StackOverflow": "https://stackoverflow.com/users/",
    "ResearchGate": "https://researchgate.net/profile/",
    "YouTube": "https://youtube.com/@",
    "Google Scholar": "https://scholar.google.com/citations?user=",
    "Telegram": "https://t.me/",
    "WhatsApp": "https://wa.me/",
    "Leetcode": "https://leetcode.com/u/",
    "X": "https://x.com/",
    "Bluesky": "https://bsky.app/profile/",
    "Reddit": "https://reddit.com/user/",
}


class SocialNetwork(BaseModelWithoutExtraKeys):
    network: SocialNetworkName | SkipJsonSchema[str] = pydantic.Field()
    username: str = pydantic.Field(
        examples=["john_doe", "@johndoe@mastodon.social", "12345/john-doe"],
    )
    url: pydantic.HttpUrl | None = pydantic.Field(
        default=None,
        description=(
            "Required for custom networks. Auto-generated for built-in networks."
        ),
    )
    fontawesome_icon: str | None = pydantic.Field(
        default=None,
        description=(
            "FontAwesome icon name (e.g. 'briefcase'). Required for custom networks."
            " See https://fontawesome.com/search for available icons (Free/Solid only)."
        ),
    )

    @pydantic.field_validator("username")
    @classmethod
    def check_username(cls, username: str, info: pydantic.ValidationInfo) -> str:
        """Validate username format per network's requirements.

        Why:
            Different platforms have specific username formats (e.g., Mastodon needs
            @user@domain, StackOverflow needs id/name). Early validation prevents
            broken URL generation. Custom networks skip all username validation.

        Args:
            username: Username to validate.
            info: Validation context containing network field.

        Returns:
            Validated username.
        """
        if "network" not in info.data:
            # the network is either not provided or not one of the available social
            # networks. In this case, don't check the username, since Pydantic will
            # raise an error for the network.
            return username

        network = info.data["network"]

        # Custom networks have no format requirements.
        if network not in available_social_networks:
            return username

        match network:
            case "Mastodon":
                mastodon_username_pattern = r"@[^@]+@[^@]+"
                if not re.fullmatch(mastodon_username_pattern, username):
                    raise pydantic_core.PydanticCustomError(
                        CustomPydanticErrorTypes.other.value,
                        'Mastodon username should be in the format "@username@domain".',
                    )
            case "StackOverflow":
                stackoverflow_username_pattern = r"\d+\/[^\/]+"
                if not re.fullmatch(stackoverflow_username_pattern, username):
                    raise pydantic_core.PydanticCustomError(
                        CustomPydanticErrorTypes.other.value,
                        "StackOverflow username should be in the format"
                        ' "user_id/username".',
                    )
            case "YouTube":
                if username.startswith("@"):
                    raise pydantic_core.PydanticCustomError(
                        CustomPydanticErrorTypes.other.value,
                        'YouTube username should not start with "@". Remove "@" from'
                        ' the beginning of the username."',
                    )
            case "ORCID":
                orcid_username_pattern = r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]"
                if not re.fullmatch(orcid_username_pattern, username):
                    raise pydantic_core.PydanticCustomError(
                        CustomPydanticErrorTypes.other.value,
                        "ORCID username should be in the format 'XXXX-XXXX-XXXX-XXX'.",
                    )
            case "IMDB":
                imdb_username_pattern = r"nm\d{7}"
                if not re.fullmatch(imdb_username_pattern, username):
                    raise pydantic_core.PydanticCustomError(
                        CustomPydanticErrorTypes.other.value,
                        "IMDB name should be in the format 'nmXXXXXXX'.",
                    )
            case "Bluesky":
                bluesky_username_pattern = r"^([a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$"
                if not re.fullmatch(bluesky_username_pattern, username):
                    raise pydantic_core.PydanticCustomError(
                        CustomPydanticErrorTypes.other.value,
                        "Bluesky username should be a valid handle with no '@' (e.g.,"
                        " 'username.bsky.social' or 'domain.com').",
                    )
            case "WhatsApp":
                try:
                    pydantic.TypeAdapter[pydantic_phone_numbers.PhoneNumber](
                        pydantic_phone_numbers.PhoneNumber
                    ).validate_python(username)
                except pydantic.ValidationError as e:
                    raise pydantic_core.PydanticCustomError(
                        CustomPydanticErrorTypes.other.value,
                        "WhatsApp username should be your phone number with country"
                        " code in international format (e.g., +1 for USA, +44 for UK).",
                    ) from e
            case "Reddit":
                reddit_username_pattern = r"^[a-zA-Z0-9_-]{3,23}$"
                if not re.fullmatch(reddit_username_pattern, username):
                    raise pydantic_core.PydanticCustomError(
                        CustomPydanticErrorTypes.other.value,
                        "Reddit username should be made up of uppercase/lowercase"
                        " letters, numbers, underscores, and hyphens between 3 and 23"
                        " characters.",
                    )

        return username

    @pydantic.model_validator(mode="after")
    def validate_network_config(self) -> "SocialNetwork":
        """Validate that custom networks have required fields, built-ins have valid URLs.

        Why:
            Custom networks need explicit url and fontawesome_icon since they cannot
            be auto-generated. Built-in networks auto-generate their URL from username,
            which needs to be validated as well-formed.

        Returns:
            Validated social network instance.
        """
        if self.network not in available_social_networks:
            if self.url is None:
                raise pydantic_core.PydanticCustomError(
                    CustomPydanticErrorTypes.other.value,
                    f'Custom network "{self.network}" requires a `url` field.',
                )
            if self.fontawesome_icon is None:
                raise pydantic_core.PydanticCustomError(
                    CustomPydanticErrorTypes.other.value,
                    f'Custom network "{self.network}" requires a `fontawesome_icon`'
                    " field. See https://fontawesome.com/search (Free/Solid icons).",
                )
        else:
            url_validator.validate_strings(self.profile_url)
        return self

    @functools.cached_property
    def profile_url(self) -> str:
        """Generate or return the profile URL.

        Why:
            Built-in networks auto-generate URLs from username + base URL.
            Custom networks use the user-provided url field directly.
            Cached to avoid repeated computation for repeated template access.

        Returns:
            Complete profile URL as string.
        """
        if self.network not in available_social_networks:
            return str(self.url)
        if self.network == "Mastodon":
            _, username, domain = self.username.split("@")
            return f"https://{domain}/@{username}"
        return url_dictionary[self.network] + self.username
