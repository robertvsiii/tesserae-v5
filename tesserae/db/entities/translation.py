"""Database standardization for text translations.

Classes
-------
Unit
    Text translation data model.
"""
import typing

from bson.objectid import ObjectId

from tesserae.db.entities.entity import Entity
from tesserae.db.entities.text import Text


class Translation(Entity):
    """Translation of a unit.

    Units are the chunks of text that matches are computed on. Units can
    come in the flavor of lines in a poem, sentences, paragraphs, etc.

    Parameters
    ----------
    id : bson.ObjectId, optional
        Database id of the text. Should not be set locally.
    text : str, optional
        The text that contains this unit.
    unit : bson.ObjectId, optional
        Database id of the translated unit.
    index : int, optional
        The order of this unit in the text. This is relative to Units of a
        particular type.
    unit_type : str, optional
        How the chunk of text in this Unit was defined, e.g., "line",
        "phrase", etc.
    tokens : list of tesserae.db.Token or bson.objectid.ObjectId, optional
        The tokens that make up this unit.
    model : str, optional
        The GPT model (or human author) used to make the translation
    snippet : str, optional
        The whole translated unit.

    Attributes
    ----------
    id : bson.ObjectId
        Database id of the text. Should not be set locally.
    text : str
        The text that contains this unit.
    unit : bson.ObjectId, optional
        Database id of the translated unit.
    index : int
        The order of this unit in the text. This is relative to Units of a
        particular type.
    tags : list of str
        The in-text locale tag(s) associated with the unit. Correponds to,
        e.g., lines of a poem or sentences/paragraphs of prose.
    unit_type : str
        How the chunk of text in this Unit was defined, e.g., "line",
        "phrase", etc.
    model : str, optional
        The GPT model (or human author) used to make the translation
    tokens : list of tesserae.db.Token or bson.objectid.ObjectId
        The tokens that make up this unit.
    notes : str, optional
	Notes on the translation of this passage
    snippet : str, optional
        The whole translated unit.
        
    """

    collection = 'translations'

    def __init__(self, id=None, text=None, index=None, tags=None, unit_type=None,
                 unit=None, model=None, tokens=None, notes=None, snippet=None):
        super(Translation, self).__init__(id=id)
        self.unit: typing.Optional[typing.Union[ObjectId, Unit]] = unit
        self.text: typing.Optional[typing.Union[ObjectId, Text]] = text
        self.index: typing.Optional[int] = index
        self.tags: typing.List[str] = tags if tags is not None else []
        self.unit_type: typing.Optional[str] = unit_type
        self.model: typing.Optional[str] = model
        self.tokens: typing.List[int] = \
            tokens if tokens is not None else []
        self.notes: typing.Optional[str] = notes
        self.snippet: typing.Optional[str] = snippet

    def json_encode(self, exclude=None):
        self._ignore = [self.text]
        if isinstance(self.text, Entity):
            self.text = self.text.id

        obj = super(Translation, self).json_encode(exclude=exclude)

        self.text = self._ignore[0]
        del self._ignore

        return obj

    def unique_values(self):
        uniques = {
            'text': self.text.id if isinstance(self.text, Entity) else self.text,
            'index': self.index,
            'unit_type': self.unit_type}
        return uniques

    def __repr__(self):
        return (
            f'Translation(unit={self.unit}, text={self.text}, index={self.index}, tags={self.tags}, '
            f'unit_type={self.unit_type}, model={self.model}, tokens={self.tokens}, '
            f'notes={self.notes}, snippet={self.snippet})'
        )
