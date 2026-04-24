"""Adapter for data.gov.tw dataset resources that contain actual public-document rows."""

from __future__ import annotations

import requests

from .reader import DataGovTwAdapter

__all__ = ["DataGovTwAdapter", "requests"]
