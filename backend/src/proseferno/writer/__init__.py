"""Write a post: dials, plan, draft, critique and revise, feedback tweaks and text version history."""

from proseferno.writer.dials import Dials, ResolvedDials, classify_topic, resolve
from proseferno.writer.pipeline import (
    WriterError,
    WrittenPost,
    ensure_placeholders,
    generate_article,
    merge_titles,
    normalize_slots,
    regenerate_titles,
    set_title,
    split_title,
    write_post,
)
from proseferno.writer.revisions import MAX_REVISIONS, push_revision, word_count
from proseferno.writer.schemas import ArticlePlan, Critique, ImageSlot, PostEdits, TextEdit, TitleOptions
from proseferno.writer.section import SECTION_ACTIONS, SectionAction, rewrite_passage
from proseferno.writer.tweak import TEXT_JOBS, apply_edits, finish_text, tweak_post

__all__ = [
    "MAX_REVISIONS",
    "SECTION_ACTIONS",
    "TEXT_JOBS",
    "ArticlePlan",
    "Critique",
    "Dials",
    "ImageSlot",
    "PostEdits",
    "ResolvedDials",
    "SectionAction",
    "TextEdit",
    "TitleOptions",
    "WriterError",
    "WrittenPost",
    "apply_edits",
    "classify_topic",
    "ensure_placeholders",
    "finish_text",
    "generate_article",
    "merge_titles",
    "normalize_slots",
    "push_revision",
    "regenerate_titles",
    "resolve",
    "rewrite_passage",
    "set_title",
    "split_title",
    "tweak_post",
    "word_count",
    "write_post",
]
