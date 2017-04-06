import pandas as pd
import numpy as np
import re
import nltk
import string
from nltk.corpus import stopwords
from nltk.stem.snowball import SnowballStemmer
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.pipeline import Pipeline
from sklearn.model_selection import GridSearchCV

stopwords = set(stopwords.words('english'))


class NewsAnalysis(object):
    def __init__(self, voxfile, jezebelfile):
        vox = self.read(voxfile, jezebelfile)
        vox = self.clean(vox)
        vox, topic_word_assoc = self.lda(vox)
        self.vox = vox
        self.topic_word_assoc = topic_word_assoc

    @staticmethod
    def read(voxfile, jezebelfile):
        vox = pd.read_json('./data/' + voxfile, lines=True)
        jezebel = pd.read_json('./data/' + jezebelfile, lines=True)
        return vox

    @staticmethod
    def clean(vox):
        vox['id'] = vox._id.apply(lambda x: x['$oid'])
        vox.drop('_id', axis=1, inplace=True)
        trans = str.maketrans('', '', string.punctuation + '0123456789')
        stemmer = SnowballStemmer('english')

        def filter_func(document):
            result = []
            wordlist = nltk.word_tokenize(document.lower().translate(trans))
            for word in wordlist:
                c1 = word not in stopwords
                c2 = len(word) > 2
                c3 = not word.startswith('https')
                c4 = not re.match('document[a-z]+', word)
                if c1 and c2 and c3 and c4:
                    result.append(stemmer.stem(word.encode('ascii', 'ignore').decode('UTF-8')))
            return result

        vox.text = vox.text.apply(lambda x: filter_func(x))
        vox_date = vox.date.apply(
            lambda x: x[:-1] + 'AM' if x.endswith('a') else x[:-1] + 'PM' if x.endswith('p') else x)
        vox_date = vox_date.apply(lambda x: x[:12] if x.endswith('M') else x)

        for row in vox_date.iteritems():
            try:
                if row[1] == 'NULL':
                    vox_date[row[0]] = np.nan
                else:
                    vox_date[row[0]] = pd.to_datetime(row[1])
            except:
                pass

        vox.date = vox_date
        return vox

    @staticmethod
    def lda(vox):
        pipeline = Pipeline([
            ('tf', CountVectorizer()),
            ('lda', LatentDirichletAllocation(learning_method='online', max_iter=30))
        ])

        parameters = {
            'lda__n_topics': range(5, 6)
        }

        gs = GridSearchCV(pipeline, parameters)
        gs.fit(vox.text.apply(lambda x: ' '.join(x)))

        topic_word_assoc = []

        def get_top_words(model, feature_names, n_top_words):
            for topic_idx, topic in enumerate(model.components_):
                topic_word_assoc.append([feature_names[i] for i in topic.argsort()[:-n_top_words - 1:-1]])

        tf_feature_names = gs.best_estimator_.steps[0][1].get_feature_names()
        lda = gs.best_estimator_.steps[1][1]
        get_top_words(lda, tf_feature_names, 10)
        topic_matrix = gs.transform(vox.text.apply(lambda x: ' '.join(x)))
        topic_df = pd.DataFrame(topic_matrix)
        topic_df.columns = ['topic' + str(t) for t in topic_df.columns]
        topic_df['max_category'] = topic_df.apply(lambda x: x.index[x == np.max(x)][0], axis=1)
        vox = pd.concat([vox, topic_df], ignore_index=True, axis=1)
        return vox, topic_word_assoc


if __name__ == '__main__':
    na = NewsAnalysis('voxtest.jsonl', 'jezebeltest.jsonl')
