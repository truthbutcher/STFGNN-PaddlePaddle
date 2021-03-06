import time
import json
import argparse

import numpy as np
import paddle
import pgl

from pgl.utils.logger import log 
from utils import (construct_model, generate_data, calc_acc, gen_batch)

def main(args):
    
    with open(args.config, 'r') as f:
        config = json.loads(f.read())
    
    print(json.dumps(config, sort_keys=True, indent=4))
    
    model = construct_model(config)

    batch_size = config['batch_size']
    num_of_vertices = config['num_of_vertices']
    graph_signal_matrix_filename = config['graph_signal_matrix_filename']
    n_his = config['num_of_history']
    n_pred = config['num_for_predict']
    epochs = config['epochs']   
    if config['use_gpu'] == "True":
        paddle.set_device("gpu")    

    loaders = []
    true_values = []

    for idx, (x, y) in enumerate(generate_data(graph_signal_matrix_filename)):
        if args.test:
            x = x[:100]
            y = y[:100]
        y = y.squeeze(axis=-1)
        if idx == 0:
            loaders.append([(x_batch,y[num_of_batch*batch_size:(num_of_batch+1)*batch_size]) for num_of_batch, x_batch in enumerate(gen_batch(x, batch_size, dynamic_batch=False, shuffle=False))])
            training_samples = x.shape[0]
        else:
            loaders.append((x,y))
            true_values.append(y)
    
    train_loader = loaders[0]
    val_loader = loaders[1]
    test_loader = loaders[2]
 
    x_val, y_val = val_loader
    opt = config['optimizer']
    lr = paddle.optimizer.lr.PolynomialDecay(learning_rate=config['learning_rate'], decay_steps=20, verbose=True)
    
    if opt == 'RMSProp':
        optim = paddle.optimizer.RMSProp(learning_rate=lr, parameters=model.parameters())
    elif opt == 'adam' or 'Adam':
        optim = paddle.optimizer.Adam(learning_rate=lr, parameters=model.parameters())
    
    

    num_of_parameters = 0
    trainable = 0
    nontrainable = 0

    for p in model.parameters():
        mulValue = np.prod(p.shape)  
        num_of_parameters += mulValue 
        if p.stop_gradient:
            nontrainable += mulValue  
        else:
            trainable += mulValue  
    
    print('total parameters: %s, trainable parameters: %s, nontrainbale parameters: %s' %(num_of_parameters, trainable, nontrainable))
    lowest_val_loss = 1e6
    for epoch in range(epochs):
        t = time.time()
        acc_list = []
        for idx, (x_batch, y_batch) in enumerate(train_loader):
            #shape of x_batch (B, n_his+n_pred, N, 1)
            x = np.array(x_batch, dtype=np.int32)
            y = np.array(y_batch, dtype=np.int32)
            #model takes it input in the form of (B, n_his+n_pred, N, 1) to generate an pred array of (n_his, num_class) and the loss
            #the training accuracy of one epoch is by calculating the mean of the prediction of every batch 
            
            loss, yhat = model(x, y)
            #shape of y is (B, n_pred, N)
            #yhat is a list of length n_pred, each entry of shape B, N
            acc = calc_acc(y, yhat)
            acc_list.append(acc)
            loss.backward()
            
            optim.minimize(loss)
            optim.clear_grad()
            if idx % 5 == 0:
                print(epoch, idx, loss)
        
        
        print('training: Epoch: %s, ACC: %.4f, time: %.2f' % (epoch, np.mean(acc_list),time.time() - t))
        #The entrire val set is view as a single batch, batch_size is fixed to be equal to length of val set and test set
        x_val, y_val = val_loader
        x_val = np.array(x_val, dtype=np.int32)
        y_val = np.array(y_val, dtype=np.int32)
        loss_val, y_hat_val = model(x_val, y_val)
        acc_val = calc_acc(y_val, y_hat_val) 
        print('validation: Epoch: %s, ACC: %.4f, time: %.2f' % (epoch, acc_val, time.time() - t))   
        if loss_val < lowest_val_loss:
            x_test, y_test = test_loader
            x_test = np.array(x_test, dtype=np.int32)
            y_test = np.array(y_test, dtype=np.int32)
            
            loss_test, y_hat_test = model(x_test, y_test)
            acc_test = calc_acc(y_test, y_hat_test)

            print('test: Epoch: %s, ACC: %.4f, time: %.2f' % (epoch, acc_test, time.time() - t))
            lowest_val_loss = loss_val[0]

    
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, help='configuration file')
    parser.add_argument("--test", action="store_true", help="test program")
    parser.add_argument("--plot", help="plot network graph", action="store_true")
    parser.add_argument("--save", action="store_true", help="save model")
    args = parser.parse_args()
    log.info(args)
    config_filename = args.config

    main(args)

