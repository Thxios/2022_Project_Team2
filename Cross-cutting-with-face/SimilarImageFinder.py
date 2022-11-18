from yoloface.face_detector import YoloDetector
from PIL import Image
import numpy as np
import pandas as pd
from util.distance import findEuclideanDistance
from itertools import combinations
from util.VideoCapture import VideoCapture
from util.functions import get_all_images, plot_by_cv2


class SimilarImageFinder:
    def __init__(self, detector, video_name, video_path, period=30, video_capture=True):
        if video_capture:
            # 영상 -> 이미지
            VideoCapture(period, video_name, video_path)
            # 같은 프레임의 이미지들 중에서 적어도 2번 이상 사람이 감지된 프레임만 추출해서 data frame 생성
            df = self._make_df_detection_by_detector(detector, video_name)
        else:
            df = pd.read_parquet(f'./dataset/{video_name}/detection_data/yoloface_data.parquet')
        # 유사한 이미지 탐색
        similarity_list = self.find_similarity_images(df)
        # 이미지 출력
        plot_by_cv2(similarity_list, video_name)

    def _sort_by_x1(self, boxes):
        """
        감지한 boundary box list 를 x1이 작은 순서대로 (왼쪽부터) 정렬하는 함수입니다.
        """
        boxes = sorted(boxes, key=lambda x: x[0][0])
        return boxes

    def _zip_person(self, boxes, points):
        """
        box 와 landmark 의 리스트를 각 사람의 box 와 landmark 로 합치는 함수입니다.
        """
        person = zip(boxes[0], points[0])
        return list(person)

    def _make_df_detection_by_detector(self, detector, video_name):
        """
        Face Detection 데이터 프레임을 만드는 함수입니다.
        :param: detector ['opencv', 'ssd', 'mtcnn', 'retinaface', 'yoloface]
        :return:
        """
        df_detection = pd.DataFrame(columns=['frame_num', 'video_num', 'detect_person_num', 'boxes', 'landmarks'])
        images = get_all_images(video_name) # 모든 이미지 경로를 가져옵니다.
        if detector == 'yoloface':
            try:
                yolo_detector = YoloDetector(target_size=720, gpu=1, min_face=90)
                print('gpu 사용')
            except:
                yolo_detector = YoloDetector(target_size=720, gpu=-1, min_face=90)
                print('cpu 사용')
            for image in images:
                # 영상 번호
                video_num = image.split('/')[-1][:-4]  # [:-4] -> .jpg remove
                # frame 번호
                frame_num = image.split('/')[-2]
                # 이미지 경로 -> ndarray
                image = np.array(Image.open(image))
                # get boundary box and landmarks
                boxes, points = yolo_detector.predict(image)
                # 감지된 사람 중 왼쪽에 있는 사람 순(x1이 작은 순)으로 정렬
                people = self._sort_by_x1(self._zip_person(boxes, points))
                # 1명 이상인 경우 / 1명만 검출하고 싶으면 == 1 로 변경
                if len(people) > 0:
                    data = {
                        'frame_num': int(frame_num),
                        'video_num': int(video_num),
                        'detect_person_num': len(people),
                        'boxes': [person[0] for person in people],
                        'landmarks': [person[1] for person in people]
                    }
                    df_detection = df_detection.append(data, ignore_index=True)
                    print(f'{frame_num}번 째 frame : {video_num} 영상 이미지 저장')
        else:
            print('아직 미구현, Deepface Detector 는 얼굴을 추출하기 때문에 customizing 필요합니다')
        # frame_num 순으로 정렬
        df_detection = df_detection.sort_values(by='frame_num')
        # filter 된 dataframe
        df_filtered = self._filter_df(df_detection)
        # 데이터프레임 저장
        df_filtered.to_parquet(f'./dataset/{video_name}/detection_data/yoloface_data.parquet')

        return df_filtered

    def _filter_df(self, df):
        """
        얼굴을 감지한 데이터프레임에서 감지된 사람 수가 같은 데이터만 추출하여 데이터프레임을 만듭니다.
        """
        # 같은 프레임의 이미지들 중에서 적어도 2번 이상 사람이 감지된 프레임만 추출
        frame_index = df['frame_num'].value_counts()[df['frame_num'].value_counts() > 1].index
        # 'frame_num' index 설정
        df = df.set_index('frame_num')

        # 빈 df_filtered 생성
        df_filtered = pd.DataFrame(
            columns=['frame_num', 'video_num', 'detect_person_num', 'boxes', 'landmarks']
        ).set_index('frame_num')

        for frame_num in frame_index:
            df1 = df.loc[frame_num]
            mask = df1.loc[frame_num].duplicated(['detect_person_num'], keep=False)
            df_filtered = pd.concat([df_filtered, df1.loc[mask]])
        return df_filtered

    def find_similarity_images(self, df_filtered):
        similarity_list = []
        for frame in df_filtered.index.unique():
            df_temp = df_filtered.loc[frame]
            # 감지된 사람 수
            detect_person_num = df_temp['detect_person_num'].iloc[0]
            # 영상 번호 리스트
            video_num_list = list(df_temp['video_num'])
            # 선택된 영상 번호
            selected_video = None
            # 거리
            dis_min = 100000000

            for selected_video_nums in list(combinations(video_num_list, 2)):
                videonum1, videonum2 = selected_video_nums[0], selected_video_nums[1]

                landmarks = list(
                    df_temp.loc[(df_temp['video_num'] == videonum1) | (df_temp['video_num'] == videonum2)]['landmarks'])
                dis = findEuclideanDistance(landmarks[0], landmarks[1], detect_person_num)
                if dis < dis_min:
                    dis_min = dis
                    selected_video = selected_video_nums
            similarity_list.append((frame, selected_video, dis_min))
        similarity_list = sorted(similarity_list, key=lambda x: x[2])
        return similarity_list


if __name__ == '__main__':
    video_path = '/Users/jungsuplim/Desktop/origin_video'
    # video capture 생략하고 싶으면 False
    SimilarImageFinder('yoloface', 'iu_lilac3', video_path, period=900, video_capture=False)

