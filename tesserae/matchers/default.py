from collections import OrderedDict
from operator import itemgetter
import re

import numpy as np
import pymongo

from tesserae.db import Match

# TODO: implement probabilistic stem matching once that's worked out


class DefaultMatcher(object):
    """Intertext matching using the Tesserae v3 similarity scoreself.

    Based on the similarity score described in [tess]_ .

    Parameters
    ----------
    connection : tesserae.db.TessMongoConnection
        Open connection to the Tesserae MongoDB instanceself.

    Attributes
    ----------
    connection : tesserae.db.TessMongoConnection
        Open connection to the Tesserae MongoDB instanceself.
    matches : list of tesserae.db.Match

    References
    ----------
    .. [tess] Forstall, C., Coffee, N., Buck, T., Roache, K., & Jacobson, S.
       (2014). Modeling the scholars: Detecting intertextuality through
       enhanced word-level n-gram matching. Digital Scholarship in the
       Humanities, 30(4), 503-515.
    """
    def __init__(self, connection):
        self.connection = connection
        self.clear()

    def clear(self):
        """Reset this Matcher to its initial state."""
        self.matches = []

    def frequency_distance(self, frequency_vector):
        """Compute distance based on frequency.

        The frequency distance computes the unmber of words separating the two
        match words with the lowest frequency in the unit.

        Parameters
        ----------
        frequency_vector : list of float
            The frequencies of the tokens.

        Returns
        -------
        distance : float
            The number of words separating the two lowest-frequency tokens.
        """
        frequency_vector = np.asarray(frequency_vector)

        # Lexical sort the frequencies first by token index in the unit, then
        # by the frequency of the token.
        idx_sorted = np.argsort(frequency_vector[:, :, 1], axis=1)
        freq = np.take_along_axis(frequency_vector[:, :, 0], idx_sorted, axis=-1)
        freq_sorted = np.argsort(freq, axis=1)
        idx = np.take_along_axis(
            np.take_along_axis(frequency_vector[:, :, 1], idx_sorted, axis=-1),
            freq_sorted, axis=-1)
        freq = np.take_along_axis(freq, freq_sorted, axis=-1)

        # Find the index of the first occurrence of each unique frequency
        # value.
        _, unique_idx = np.unique(freq, return_index=True, axis=1)

        # Account for repeated frequency values.
        if unique_idx.shape[0] > 1:
            unique_idx[unique_idx > 1] -= 1
            end = unique_idx[1]
        else:
            end = freq.shape[1] - 1

        # The distance is the number of words separating the two least-frequent
        # tokens, taking the maximum possible distance when multiple tokens
        # occur at the lowest frequency.
        return np.abs(idx[:, end] - idx[:, 0]) + 1

    def match(self, texts, unit_type, feature, stopwords=10,
              stopword_basis='corpus', score_basis='word',
              frequency_basis='texts', max_distance=10,
              distance_metric='frequency'):
        """Find matches between one or more texts.

        Texts will contain lines or phrases with matching tokens, with varying
        degrees of strength to the match. If one text is provided, each unit in
        the text will be matched with every subsequent unit.

        Parameters
        ----------
        texts : list of tesserae.db.Text
            The texts to match. Texts are matched in
        unit_type : {'line','phrase'}
            The type of unit to match on.
        feature : {'form','lemmata','semantic','lemmata + semantic','sound'}
            The token feature to match on.
        stopwords : int or list of str
            The number of stopwords to use, to be retrieved from the database,
            or else a list of words to use as stopwords.
        stopword_basis : {'corpus','texts'} or slice or tesserae.db.Text
            Which frequencies to use when calculating the stoplist.
            - 'corpus': use the combined frequencies of the entire corpus
            - 'texts': use the combined frequencies of all texts in the match
            - slice: use the texts returned from `texts` by the slice
            - Text: use a single text
        score_basis : {'word','stem'}
            Whether to score based on the words (normalized text) or stems
            (lemmata).
        frequency_basis : {'texts','corpus'}
            Take frequencies from the texts being matched or from the entire
            corpus.
        max_distance : float
            The maximum inter-word distance to use in a match.
        distance_metric : {'frequency', 'span'}
            The methods used to compute distance.
            - 'frequency': the distance between the two least frequent words
            - 'span': the greatest distance between any two matching words
        """
        # Get the units, tokens, and frequencies to match on
        tokens = self.retrieve_tokens(texts)
        units = self.retrieve_units(texts, unit_type)
        frequencies, stopwords = \
            self.retrieve_frequencies(texts, tokens,
                                      frequency_basis, stopwords)

        print('Stopwords: {}'.format(stopwords))

        # TODO: recursive scheme for matching

        matches = []
        distance_function = self.span_distance if distance_metric == 'span' \
            else self.frequency_distance

        for unit_a in units[0]:
            for unit_b in units[1]:
                match = Match(units=[unit_a, unit_b])
                match_tokens = [[], []]
                distance_vector = [[], []]
                match_frequencies = [[], []]
                tokens_a = [tokens[0][t] for t in unit_a.tokens]
                tokens_b = [tokens[1][t] for t in unit_b.tokens]
                for token_a in tokens_a:
                    if not token_a.form or not re.search(r'[\w]', token_a.form, flags=re.UNICODE) or token_a.form in stopwords:
                        continue
                    for token_b in tokens_b:
                        if not token_b.form or not re.search(r'[\w]', token_b.form, flags=re.UNICODE) or token_b.form in stopwords:
                            continue
                        if token_a.match(token_b, feature):
                            match_tokens[0].append(token_a)
                            match_frequencies[0].append(frequencies[token_a.form])
                            match_tokens[1].append(token_b)
                            match_frequencies[1].append(frequencies[token_b.form])
                            if distance_metric == 'span':
                                distance_vector[0].append(token_a.index)
                                distance_vector[1].append(token_b.index)
                            elif distance_metric == 'frequency':
                                distance_vector[0].append(
                                    (frequencies[token_a.form], token_a.index))
                                distance_vector[1].append(
                                    (frequencies[token_b.form], token_b.index))

                if len(match_tokens[0]) < 2 or len(match_tokens[1]) < 2:
                    continue

                dist = distance_function(distance_vector).astype(np.float32)

                if np.all(dist > 1) and np.all(dist <= max_distance):
                    dist = sum(dist)
                    freq = np.sum(
                        np.sum(1.0 / np.asarray(match_frequencies).astype(np.float32), axis=-1))
                    match.score = np.log(freq / dist)
                    match.match_tokens = match_tokens
                    matches.append(match)

        self.matches.extend(matches)
        return matches

    def retrieve_frequencies(self, texts, tokens, basis, stoplist=None):
        """Get token frequencies for the tokens to be matched.

        Parameters
        ----------
        texts : 'corpus' or list of tesserae.db.Text
            The texts from which to compute the token frequencies. If 'corpus',
            use token frequencies from the entire collection of texts in the
            database. Otherwise, use frequencies within the specified texts.

        tokens : list of tesserae.db.Token
            The tokens that should be included in the match.
        basis : {'word', 'stem'}


        Returns
        -------
        frequencies : dict
            Key/value pairs of frequencies indexed by text and token string:
            {{
                <text_id>: {{
                    <token_string>: <frequency>
                }}
            }}
        """
        if basis == 'corpus':
            frequencies = self.connection.find(
                'frequencies',
                sort=[('frequency', pymongo.DESCENDING)])
        else:
            frequencies = self.connection.find(
                'frequencies',
                sort=[('frequency', pymongo.DESCENDING)],
                text=[t.path for t in texts])

        formatted = OrderedDict()
        for f in frequencies:
            try:
                formatted[f.form] += f.frequency
            except KeyError:
                formatted[f.form] = f.frequency

        stopwords = []
        if stoplist:
            stopwords = sorted(formatted.items(), key=lambda x: x[1], reverse=True)
            stopwords = [i[0] for i in stopwords]
            stopwords = stopwords[:stoplist]

        return formatted, stopwords

    def retrieve_tokens(self, texts):
        """Get the tokens associated with a text from the database.

        Parameters
        ----------
        text : tesserae.db.Text
            Text metadata.

        Returns
        -------
        tokens : list of tesserae.db.Token
            The tokens in the order they appear in the original text.
        """
        tokens = []

        for text in texts:
            tokens.append(self.connection.find(
                'tokens',
                sort=[('index', pymongo.ASCENDING)],
                text=text.id))

        return tokens

    def retrieve_units(self, texts, unit_type):
        """Get the units associated with a text from the database.

        Parameters
        ----------
        text : tesserae.db.Text
            Text metadata.
        unit_type : {'line','phrase'}
            The type of unit to retrieve.

        Returns
        -------
        units : list of tesserae.db.Unit
            The units in the order they appear in the original text.
        """
        units = []

        for text in texts:
            units.append(self.connection.find('units',
                         sort=[('index', pymongo.ASCENDING)],
                         text=text.path, unit_type=unit_type))
        return units

    def span_distance(self, index_vector):
        """Compute distance based on position in the text.

        The span distance computes the number of words separating the first and
        final match words in the unit.

        Parameters
        ----------
        index_vector : list of int
            The indices of the match tokens.

        Returns
        -------
        distance : float
            The number of words separating the two lowest-frequency tokens.
        """
        index_vector = np.asarray(index_vector)

        # Sort the indices of the match words in each unit.
        ordered = np.argsort(index_vector, kind='heapsort', axis=-1)

        # The distance of the match in each unit is the number of words
        # spearating the first and last match words.
        dist = np.abs(
            np.take_along_axis(index_vector, ordered, axis=-1)[:, -1] -
            np.take_along_axis(index_vector, ordered, axis=-1)[:, 0]) + 1

        # if np.any(dist < 2):
        #     raise ValueError(
        #         "The index vector must contain multiple values and cannot " +
        #         "contain duplicate values")

        return dist
