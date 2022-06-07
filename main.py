import os
import pandas as pd
from time import time
from sklearn.metrics import classification_report
from pathlib import Path
from src.data import ClearingPhrases
from src.models import Classifier


class ModelTraining:
    run_model = False

    def __init__(self, train_file: str, classifier: Classifier, clearing: ClearingPhrases = None):
        self.clearing = clearing
        self.classifier = classifier
        self.train = pd.read_csv(self.path(train_file)).sort_values('frequency', ascending=False)[
            ['phrase', 'subtopic']]
        self.init_df = self.__init_df('data/input/parfjum_classifier.csv', 'data/model/in_model.csv')

    @staticmethod
    def path(path):
        return Path(os.getcwd(), path)

    def __init_df(self, path: str, save_path: str) -> pd.DataFrame:
        df = pd.read_csv(self.path(path)).fillna(method="pad", axis=1)['Подтема'].dropna().values
        df = pd.DataFrame({'phrase': df, 'subtopic': df, 'subtopic_true': df})
        self.train['subtopic_true'] = self.train['subtopic']
        df.to_csv(self.path(save_path), index=False)
        return df

    # Upgrade to implementation from PyTorch
    def batch(self, batch_size: int) -> pd.DataFrame:
        return self.train[:batch_size]

    # There may be data preprocessing or it may be placed in a separate class
    def __update_init_df(self, markup: pd.DataFrame):
        '''
        Созраняем размеченные данные в таблицу. Обновляем тренировчный набор.
        :param markup: Разметка полученная разметчиками или моделью.
        '''
        self.init_df = pd.concat([self.init_df, markup], ignore_index=True)
        self.init_df.to_csv(self.path('data/model/in_model.csv'))

    def start(self, limit: float, batch_size: int):
        if not self.classifier.start_model_status:
            self.classifier.add(self.init_df['phrase'].values, self.init_df['subtopic'].values)

        people, model = 0, 0
        all_metrics, marked_metrics, marked_data = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        while self.train.shape[0]:
            if self.run_model:
                # Размечаем набор данных моделью
                index_limit, all_predict = self.classifier.predict(self.train['phrase'], limit)
                predict_df = pd.DataFrame({'phrase': self.train.loc[index_limit].phrase,
                                           'subtopic': all_predict[index_limit] if index_limit.shape[0] else [],
                                           'subtopic_true': self.train.loc[index_limit]['subtopic_true']})
                marked_data = pd.concat([marked_data, predict_df], ignore_index=True)
                self.train = self.train.drop(index=index_limit).reset_index(drop=True)
                model += index_limit.shape[0]
                self.__update_init_df(predict_df)

            # Получаем разметку и отправляем в размеченный набор данных
            batch = self.batch(batch_size=batch_size)
            self.train = self.train.drop(index=batch.index).reset_index(drop=True)
            people += batch.shape[0]
            self.__update_init_df(batch)

            if self.run_model:
                # Оцениваем качество модели на предсказнных ей
                index_limit, all_predict = self.classifier.predict(marked_data['phrase'], limit)
                metrics = self.classifier.metrics(marked_data['subtopic_true'], all_predict)
                metrics[['model_from_val', 'model_from_all', 'people_from_val']] = index_limit.shape[0], model, people
                marked_metrics = pd.concat([marked_metrics, metrics])

            # Оцениваем качество модели на всех доступных данных
            index_limit, all_predict = self.classifier.predict(self.init_df['phrase'], limit)
            metrics = self.classifier.metrics(self.init_df['subtopic_true'], all_predict)
            metrics[['model_from_val', 'model_from_all', 'people_from_val']] = index_limit.shape[0], model, people
            all_metrics = pd.concat([all_metrics, metrics])
            if metrics['precision'][0] >= 0.98:
                self.run_model = True

            # Добавляем новые индексы в модель
            self.classifier.add(self.init_df['phrase'].values, self.init_df['subtopic'])

        all_metrics.to_csv(self.path(f'data/model/{limit}_{batch_size}_all_metrics.csv'), index=False)
        marked_metrics.to_csv(self.path(f'data/model/{limit}_{batch_size}_marked_metrics.csv'), index=False)
        marked_data.to_csv(self.path(f'data/model/{limit}_{batch_size}_marked.csv'), index=False)


if __name__ == '__main__':
    # full = pd.read_csv('data/input/Parfjum_full_list_to_markup.csv')
    # clearing = ClearingPhrases(full.words_ordered.values)
    # phrases = ClearingPhrases(full.words_ordered.values).get_best_texts
    classifier = Classifier('models/adaptation/best.bin', 'models/classifier.pkl')
    system = ModelTraining('data/processed/perfumery_train.csv', classifier)
    t1 = time()
    system.start(limit=0.80, batch_size=500)
    print(time() - t1)
