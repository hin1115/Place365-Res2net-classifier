from torchvision.datasets import ImageFolder
from torch.utils.data import Dataset, DataLoader
import torchvision.transforms as transforms
import torch.nn.functional as F
from sklearn.preprocessing import OneHotEncoder
import PIL
from PIL import Image
import PIL.Image as pilimg
import torch
from torch.utils.data.sampler import SubsetRandomSampler
import torch.nn as nn
import torch.optim.lr_scheduler as lr_scheduler
import torch.optim as optim
import math
import pandas as pd
import numpy as np


import time
from model import Res2Net
from dataloader import data_generator_test
now = time.localtime()

class Inferer(object):

    def __init__(self, config):
        self.config = config        
        self.batch_size = self.config['training']['batch_size']
        self.model_name = self.config['model_name']
        self.device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        self.weight_file = self.config['weight_file']
        if self.model_name == 'Res2Net' :
            self.model = Res2Net(self.config).to(self.device)
        else : 
            print("Wrong Model Name")            
        self.model_path = self.config['result_path'] + '/'+self.weight_file
        self.num_class = self.config['training']['num_class']
        self.data_dir = self.config['data']['data_dir']
        self.test_datagen , self.count= data_generator_test(self.config, self.data_dir) 
        df =  pd.read_csv(self.data_dir + 'train.txt')
        df = df.loc[:,['class','place']]
        df = df.drop_duplicates()
        self.diction  = df.set_index('class', drop = False)
        
        # top k value?
        self.top_k_val = 2

        
    def __call__(self, infer_df=None):

        self.model.load_state_dict(torch.load(self.model_path,map_location=self.device))
        self.model.eval()
        with torch.no_grad(): 
            test_loss = 0
            idx_num = 0
            save_file_list = []
            top_k_list = []
            top_k_result_list = []
            top_k_score_list = []
            save_top_k = []
            save_score=[]
            for batch_idx, samples in enumerate(self.test_datagen):
               
                x_test, x_test_name, x_class_name,img_name = samples
                data = x_test.to(self.device)
                output_ = self.model(data)
                prob = F.softmax(output_,dim=1)
                pred = output_.argmax(dim=1, keepdim=True)
                # extract top-k indices
                score_,____ = prob.topk(self.top_k_val,dim=1)
                score_22, pred_indices = torch.topk(output_, self.top_k_val )
                for b_idx in range( len(x_test_name) ):
                       
                    #ground trurh class
                    gt_=x_test_name[b_idx].cpu().numpy().astype(int)
                    
                    #ground truth name
                    name_ = x_class_name[b_idx]
                    
                    #image root
                    image=img_name[b_idx]
                    pred_ = pred[b_idx][0].cpu().numpy().astype(int)
                    pred_name = self.diction.loc[pred_]
                    save_file_list.append([image, gt_, name_])
                    
                    # get names of top-k
                    top_k_list = []
                    top_k_score_list=[]
                    for i in range (self.top_k_val) :
                        top_k = pred_indices[b_idx][i].cpu().numpy().astype(int)
                        top_k_score = score_[b_idx][i].cpu().numpy().astype(float)
                        
                        try : 
                            top_k_name_idx = self.diction.loc[top_k]
                        except : 
                            print('no place')
                        top_k_name = top_k_name_idx[1]
                        if i == 0 :
                            top_k_list.append(top_k)
                        top_k_list.append(top_k_name)
                        top_k_score_list.append(top_k_score)
                    save_top_k.append(top_k_list)
                    save_score.append(top_k_score_list)
                    
                     #calculate top-k result
                    if gt_ in pred_indices[b_idx].cpu().numpy():
                        top_k_result_list.append(1)
                    else:
                        top_k_result_list.append(0)


                idx_num += self.batch_size
                if (batch_idx % 20 ==0) :
                    print( "iter num : {} // entire : {}".format(idx_num,self.count) )

        ## make output files
        topk_df = pd.DataFrame(save_top_k)
        score_df = pd.DataFrame(save_score)
        result_path =  self.config['result_path']
        score_df.to_csv(result_path+'/topk.csv')        
        result_df = pd.DataFrame(save_file_list)
        data_df = pd.DataFrame(save_file_list)
        result_df=pd.concat([data_df,topk_df,score_df], axis =1)
        result_df.to_csv(result_path +'./result.csv')
        
        
        print("================test completed============================")  
        print(result_df.head)
        print(topk_df.head)
        print("==========================================================")
        eval_arr = np.array(result_df)                
        accuracy = np.mean(np.equal(eval_arr[:,1],eval_arr[:,3]), dtype=np.float)
        top5acc = np.mean(top_k_result_list)        
        
        print("acuuracy =  %.6f" % accuracy)
        print("top5 accuracy = %.6f" % top5acc)


