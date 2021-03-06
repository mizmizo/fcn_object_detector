#!/usr/bin/env python

import os
import caffe
import random
import numpy as np
import cv2 as cv
import argumentation_engine as ae

class DataArgumentationLayer(caffe.Layer):

    def setup(self, bottom, top):
        #! check that inputs are pair of image and labels (bbox and label:int)
        if len(bottom) > 0:
            raise Exception('This layer takes no bottom')
        
        if len(top) < 6:
            raise Exception('Current Implementation needs 6 top blobs')

        try:
            plist = self.param_str.split(',')
            self.image_size_x = int(plist[0])
            self.image_size_y = int(plist[1])
            self.stride = int(plist[2])
            self.num_classes = int(plist[3])
            
            self.batch_size = int(plist[4])
            self.train_fn = str(plist[5]) #! dataset textfile
            #self.randomize = bool(plist[6])
            self.randomize = True

            if not os.path.isfile(self.train_fn):
                raise ValueError('Provide the dataset textfile')

            else:
                self.img_path, self.rects, self.labels = self.read_and_decode_lines()
                self.idx = 0 #! start index

            self.__ae = ae.ArgumentationEngine(self.image_size_x, self.image_size_y, \
                                               self.stride, self.num_classes)

            if self.randomize:
                random.seed()
                self.idx = random.randint(0, (len(self.img_path))-1)
            
        except ValueError:
            raise ValueError('Parameter string missing or data type is wrong!')
            
    def reshape(self, bottom, top):
        #! check input dimensions
        n_images = self.batch_size
        out_size_x = int(self.image_size_x / self.stride)
        out_size_y = int(self.image_size_y / self.stride)

        channel_stride = 4
        channels = int(self.num_classes * channel_stride)
        
        top[0].reshape(n_images, 3, self.image_size_y, self.image_size_x)
        top[1].reshape(n_images, self.num_classes, out_size_y, out_size_x) #! cvg labels  # 1
        top[2].reshape(n_images, channels, out_size_y, out_size_x) #! bbox labels # 4
        top[3].reshape(n_images, channels, out_size_y, out_size_x) #! size labels # 4
        top[4].reshape(n_images, channels, out_size_y, out_size_x) #! obj labels  # 4
        top[5].reshape(n_images, channels, out_size_y, out_size_x) #! cvg block   # 4
        

    def forward(self, bottom, top):
        for index in xrange(0, self.batch_size, 1):
            img = cv.imread(self.img_path[self.idx])
            rects = self.rects[self.idx]
            labels = self.labels[self.idx]
            
            img, rects = self.__ae.random_argumentation(img, rects)
            img, rects = self.__ae.resize_image_and_labels(img, rects)
            foreground_labels, boxes_labels, size_labels, obj_labels, coverage_label = \
            self.__ae.bounding_box_parameterized_labels(img, rects, labels)

            ##!
            # x,y,w,h = rects[0]
            # cv.rectangle(img, (x,y), (x+w, y+h), (0, 255,0), 4)
            # cv.imshow("img", img)
            # cv.waitKey(0)
            ##!
            
            img = img.swapaxes(2, 0)
            img = img.swapaxes(2, 1)

            top[0].data[index] = img
            top[1].data[index] = foreground_labels.copy()
            top[2].data[index] = boxes_labels.copy()
            top[3].data[index] = size_labels.copy()
            top[4].data[index] = obj_labels.copy()
            top[5].data[index] = coverage_label.copy()

            self.idx = random.randint(0, (len(self.img_path))-1)

    def backward(self, top, propagate_down, bottom):
        pass
        

    """
    Function to read and extract path to images, bounding boxes and the labels
    """
    def read_and_decode_lines(self):
        lines = [line.rstrip('\n')
                 for line in open(self.train_fn)
        ]
        
        if self.randomize:
            np.random.shuffle(lines)

        img_path = []
        rects = []
        labels = []
        for line in lines:
            line_val = line.split()
            img_path.append(line_val[0])
            rect = []
            for i in xrange(1, len(line_val)-1, 1):
                rect.append(int(line_val[i]))
            rect = np.array([rect])
            rects.append(rect)
            
            label = int(line_val[-1]) - 1 ##> change to auto rank
            label = np.array([label])
            labels.append(label)
        return np.array(img_path), np.array(rects), np.array(labels)

    def read_and_decode_lines2(self):
        lines = [line.rstrip('\n')
                 for line in open(self.train_fn)
        ]
        im_paths = []
        rects = []
        labels = []
        for line in lines:
            segment = line.split(',')
            im_paths.append(str(segment[0]))
            labs = []
            bbox = []
            for index in xrange(1, len(segment), 1):
                seg = segment[index].split(' ')
                bbox.append(map(int, seg[:-1]))
                labs.append(int(seg[-1]))
            labels.append(labs)
            rects.append(bbox)
        return np.array(im_paths), np.array(rects), np.array(labels)


class DataArgumentationTestLayer(caffe.Layer):

    def setup(self, bottom, top):
        pass
        
    def reshape(self, bottom, top):
        self.image_size_y = bottom[0].data.shape[2]
        self.image_size_x = bottom[0].data.shape[3]
        self.batch_size = bottom[0].data.shape[0]
    
    def forward(self, bottom, top):
        for i in xrange(0, self.batch_size, 1):
            image = bottom[0].data[i]
            image = image.transpose((1, 2, 0))
            
            # cv.namedWindow('timage', cv.WINDOW_NORMAL)
            # cv.imshow('timage', image)
            # cv.waitKey(3)

    def bottom(self, bottom, top):
        pass
