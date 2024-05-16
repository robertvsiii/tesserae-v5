"""Database standardization for vector embeddings.

Classes
-------
Unit
    Vector embedding data model.
"""
import typing

from bson.objectid import ObjectId

from tesserae.db.entities.entity import Entity
from tesserae.db.entities.text import Text


class Vector(Entity):
    """Vector embedding of a unit.

    Units are the chunks of text that matches are computed on. Units can
    come in the flavor of lines in a poem, sentences, paragraphs, etc.

    Parameters
    ----------
    id : bson.ObjectId, optional
        Database id of the vector. Should not be set locally.
    unit : bson.ObjectId, optional
        Database id of the embedded unit.
    model : str, optional
        The embedding model used to generate the vector
    vector : float, optional
        The vector embedding.
    text : str, deprecated
        The text that contains this unit.
    index : int, deprecated
        The order of this unit in the text. This is relative to Units of a
        particular type.
    unit_type : str, deprecated
        How the chunk of text in this Unit was defined, e.g., "line",
        "phrase", etc.

    Attributes
    ----------
    id : bson.ObjectId
        Database id of the text. Should not be set locally.
    unit : bson.ObjectId, optional
        Database id of the embedded unit.
    model : str, optional
        The embedding model used to generate the vector
    vector : float, optional
        The vector embedding.
    text : str
        The text that contains this unit.
    index : int
        The order of this unit in the text. This is relative to Units of a
        particular type.
    tags : list of str
        The in-text locale tag(s) associated with the unit. Correponds to,
        e.g., lines of a poem or sentences/paragraphs of prose.
    unit_type : str
        How the chunk of text in this Unit was defined, e.g., "line",
        "phrase", etc.
        
    """

    collection = 'vectors'

    def __init__(self, id=None, unit=None, model=None, vector=None, text=None, index=None, tags=None, unit_type=None):
        super(Vector, self).__init__(id=id)
        self.unit: typing.Optional[typing.Union[ObjectId, Unit]] = unit
        self.model: typing.Optional[str] = model
        self.vector: typing.Optional[float] = vector
        ##Deprecated:
        self.text: typing.Optional[typing.Union[ObjectId, Text]] = text
        self.index: typing.Optional[int] = index
        self.tags: typing.List[str] = tags if tags is not None else []
        self.unit_type: typing.Optional[str] = unit_type

    def json_encode(self, exclude=None):
        self._ignore = [self.text]
        if isinstance(self.text, Entity):
            self.text = self.text.id

        obj = super(Vector, self).json_encode(exclude=exclude)

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
            f'Vector(unit={self.unit}, text={self.text}, index={self.index}, tags={self.tags}, '
            f'unit_type={self.unit_type}, '
            f'model={self.model}, '
            f'vector={self.vector})'
        )
