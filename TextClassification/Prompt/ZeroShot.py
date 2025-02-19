import numpy as np
import time
import copy
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import torch.nn.functional
import torch.utils.data
from torch.utils.data import Dataset, DataLoader
from transformers import AdamW

import torch

from dataloader import load_train
from dataloader import load_test
from Model import BertClassifier

from transformers import BertTokenizer

import random

from config import *

def setup_seed(seed):
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    np.random.seed(seed)
    random.seed(seed)
setup_seed(44)

train_samples = load_train()
test_samples = load_test()

def convert2dataset_origin(bert_sent,masks,labels):
    masks=torch.tensor(masks)
    bert_sent=torch.tensor(bert_sent)
    labels = torch.tensor(labels)
    train_dataset = torch.utils.data.TensorDataset(bert_sent,masks,labels)
    return train_dataset

train_dataset = convert2dataset_origin(train_samples[0], train_samples[1],train_samples[2])
test_dataset = convert2dataset_origin(test_samples[0], test_samples[1],test_samples[2])

from EasyTransformer.util import ProgressBar


net = BertClassifier()
print(net)
net = net.cuda()


def test():
    net.eval()
    batch_size = 16
    avg_loss = 0
    correct = 0
    total = 0
    iter=0
    crossentropyloss = nn.CrossEntropyLoss()
    
    with torch.no_grad():
        train_iter = torch.utils.data.DataLoader(test_dataset, batch_size, shuffle=False)
        pbar = ProgressBar(n_total=len(train_iter), desc='Testing')
        for train_text,bert_sent,label in train_iter:
            iter += 1
            if train_text.size(0) != batch_size:
                break

            train_text = train_text.reshape(batch_size, -1)
            label = label.reshape(-1)


            if USE_CUDA:
                train_text=train_text.cuda()
                label = label.cuda()
                bert_sent = bert_sent.cuda()
            if Trainbert:
                logits,attn = net(bert_sent)
            else:
                logits,attn = net(train_text)
        
            loss = crossentropyloss(logits, label)
            avg_loss+=loss.item()     
            #pbar(iter, {'loss': avg_loss/iter})
            _, logits = torch.max(logits, 1)

            correct += logits.data.eq(label.data).cpu().sum()
            total += batch_size
        print("Test Acc : ", correct.numpy().tolist() / total)
        return correct.numpy().tolist() / total

def train_Kd():
    load_eval()
    teach_model = BertClassifier()
    teach_model=torch.load('./teacher.pth')
    teach_model.eval()
    teach_model = teach_model.cuda()
    
    optimizer = AdamW(net.parameters(),lr = 2e-3, eps = 1e-8)
    if Trainbert:
        optimizer = AdamW(net.parameters(),lr = 2e-5, eps = 1e-8)
    #optimizer = AdamW(net.parameters(), lr=learning_rate)
    #train_dataset, test_dataset = torch.utils.data.random_split(dataset, [train_size, test_size])
    train_iter = torch.utils.data.DataLoader(train_dataset, batch_size, shuffle=True)
    pre_loss=1
    alpha = 0.3
    criterion2 = nn.MSELoss()
    crossentropyloss = nn.CrossEntropyLoss()
    total_steps = len(train_iter)*num_epochs
    print("----total step: ",total_steps,"----")
    print("----warmup step: ", int(total_steps * 0.2), "----")
    best_acc=0
    scheduler = get_linear_schedule_with_warmup(optimizer, num_warmup_steps = int(total_steps*0.15), num_training_steps = total_steps)
    
    for epoch in range(num_epochs):
        correct = 0
        total=0
        iter = 0
        pbar = ProgressBar(n_total=len(train_iter), desc='Training')
        net.train()
        avg_loss = 0
        for train_text,bert_sent,label in train_iter:
            iter += 1
            if train_text.size(0) != batch_size:
                break

            train_text = train_text.reshape(batch_size, -1)
            label = label.reshape(-1)


            if USE_CUDA:
                train_text=train_text.cuda()
                label = label.cuda()
                bert_sent = bert_sent.cuda()

            with torch.no_grad():
                teacher_outputs,attn = teach_model(bert_sent)
            if Trainbert:
                logits,attn = net(bert_sent)
            else:
                logits,attn = net(train_text)
            
            T = 2
            outputs_S = F.softmax(logits/T,dim=1)
            outputs_T = F.softmax(teacher_outputs/T,dim=1)

            loss2 = criterion2(outputs_S,outputs_T)*T*T     
            loss = crossentropyloss(logits, label)
            loss = loss*(1-alpha) + loss2*alpha

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            scheduler.step()
            avg_loss+=loss.item()     
            pbar(iter, {'loss': avg_loss/iter})
            _, logits = torch.max(logits, 1)
            # print(logits)
            # print(label)
            # print(correct)
            # print(total)
            correct += logits.data.eq(label.data).cpu().sum()
            total += batch_size
        loss=loss.detach().cpu()
        #print("\nepoch ", str(epoch)," loss: ", loss.mean().numpy().tolist(),"Acc:", correct.numpy().tolist()/total)
        cur_acc = test()
        if best_acc < cur_acc:
            best_acc = cur_acc
            print("saved Best ACC: ",best_acc)
            torch.save(net, 'model.pth') 
    
    print(best_acc)
    return

def train():
    net.train()
    #optimizer = optim.SGD(net.parameters(), lr=0.01,weight_decay=0.01)
    #optimizer = optim.Adam(net.parameters(), lr=learning_rate,weight_decay=0)
    
    optimizer = AdamW(net.parameters(),lr = 2e-4, eps = 1e-8)
    if Trainbert:
        optimizer = AdamW(net.parameters(),lr = 2e-5, eps = 1e-8)
    #optimizer = AdamW(net.parameters(), lr=learning_rate)
    #train_dataset, test_dataset = torch.utils.data.random_split(dataset, [train_size, test_size])
    train_iter = torch.utils.data.DataLoader(train_dataset, batch_size, shuffle=True)
    pre_loss=1
    crossentropyloss = nn.CrossEntropyLoss()
    if mode == 'train_with_RDrop':
        KL_loss_function = nn.KLDivLoss()
    total_steps = len(train_iter)*num_epochs
    print("----total step: ",total_steps,"----")
    print("----warmup step: ", int(total_steps * 0.2), "----")
    best_acc=0
    scheduler = get_linear_schedule_with_warmup(optimizer, num_warmup_steps = int(total_steps*0.15), num_training_steps = total_steps)
    for epoch in range(num_epochs):
        correct = 0
        total=0
        iter = 0
        pbar = ProgressBar(n_total=len(train_iter), desc='Training')
        net.train()
        avg_loss = 0
        for train_text,bert_sent,label in train_iter:
            iter += 1
            if train_text.size(0) != batch_size:
                break

            train_text = train_text.reshape(batch_size, -1)
            label = label.reshape(-1)


            if USE_CUDA:
                train_text=train_text.cuda()
                label = label.cuda()
                bert_sent = bert_sent.cuda()
                
            if Trainbert:
                logits,attn = net(bert_sent)
            else:
                logits,attn = net(train_text)

            if mode == 'train_with_RDrop':
                logits2,attn2 = net(train_text)
                # loss1= crossentropyloss(logits, label)
                # loss2= crossentropyloss(logits2, label)
                loss = loss_pro(logits,logits2,label)      
            else:
                loss = crossentropyloss(logits, label)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            scheduler.step()
            avg_loss+=loss.item()     
            pbar(iter, {'loss': avg_loss/iter})
            _, logits = torch.max(logits, 1)
            # print(logits)
            # print(label)
            # print(correct)
            # print(total)
            correct += logits.data.eq(label.data).cpu().sum()
            total += batch_size
        loss=loss.detach().cpu()
        #print("\nepoch ", str(epoch)," loss: ", loss.mean().numpy().tolist(),"Acc:", correct.numpy().tolist()/total)
        cur_acc = test()
        if best_acc < cur_acc:
            best_acc = cur_acc
            print("saved Best ACC: ",best_acc)
            #torch.save(net, 'model.pth') 
    
    print(best_acc)
    return
    
# base 0.71875
# Attention1 0.7777777777777778
# Attention2 0.7430555555555556
# Transformer 0.7708333333333334


# 0.7048611111111112
# 0.78125
# 0.7743055555555556
# 0.71875
#train_with_FGM()

# NOVA
# trainer()
# Base 0.7465277777777778
# Attention1 0.8159722222222222
# Attention2 0.7881944444444444
# Transformer 0.7916666666666666
# BERT 0.8645833333333334


if mode ==  'train_with_FGM':
    train_with_FGM()

if mode == "train_Kd":
    train_Kd()

if mode == "train" or 'train_with_RDrop':
    train()


#train_Kd()
#train_with_FGM()

#saved Best ACC:  0.8333333333333334


#0.8194444444444444
#0.8298611111111112