from __future__ import print_function

import sys

import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import torch.backends.cudnn as cudnn
import PIL
from evaluation.gtsrb_dataset import GTSRB
sys.path.append('./FeatureLearningRotNet/architectures')

from NetworkInNetwork import NetworkInNetwork
import torchvision
import torchvision.transforms as transforms
import os
import argparse
import numpy
import random
import re

torch.backends.cudnn.deterministic = True
torch.backends.cudnn.benchmark = False
parser = argparse.ArgumentParser(description='PyTorch GTSRB Certification')
parser.add_argument('--models',  type=str, help='name of models directory')
parser.add_argument('--zero_seed', action='store_true', help='Use a random seed of zero (instead of the partition index)')

args = parser.parse_args()
root = '/cmlscratch/wwx/DPA'
checkpoint_dir = 'checkpoints'

if not os.path.exists('./evaluations'):
    os.makedirs('./evaluations')
device = 'cuda' if torch.cuda.is_available() else 'cpu'

# Data
print('==> Preparing data..')


modelnames = list(map(lambda x: root + '/checkpoints/'+args.models+'/'+x, list(filter( lambda x:x[0]!='.',os.listdir(root + '/checkpoints/'+args.models)))))
num_classes = 43
predictions = torch.zeros(12630, len(modelnames),num_classes).cuda()
labels = torch.zeros(12630).type(torch.int).cuda()
firstit = True
for i in range(len(modelnames)):
    modelname = modelnames[i]
    # seed = int(re.findall(r"FiniteAggregation_[0-9]*\.pth",  modelname)[-1][18:-4])
    if (args.zero_seed):
        seed = 0
    random.seed(seed)
    numpy.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    net  = NetworkInNetwork({'num_classes':43})
    print(modelname)
    net = net.to(device)

    checkpoint = torch.load(modelname)
    transform_test = transforms.Compose([
        # torchvision.transforms.Lambda(lambda x: PIL.ImageOps.equalize(x)), # If using histogram equalization
        torchvision.transforms.Resize((48,48),interpolation=PIL.Image.BILINEAR ),
        transforms.ToTensor(),
        transforms.Normalize(checkpoint['norm_mean'], checkpoint['norm_std'])
    ])

    testset = GTSRB('./data', train=False, transform=transform_test)
    testloader = torch.utils.data.DataLoader(testset, batch_size=400, shuffle=False, num_workers=1)

    net.load_state_dict(checkpoint['net'])
    net.eval()
    batch_offset = 0
    with torch.no_grad():
         for batch_idx, (inputs, targets) in enumerate(testloader):
            inputs, targets = inputs.cuda(), targets.cuda()
            out = net(inputs)
            predictions[batch_offset:inputs.size(0)+batch_offset,i,:] = out
            if firstit:
                labels[batch_offset:batch_offset+inputs.size(0)] = targets
            batch_offset += inputs.size(0)
    firstit = False

torch.save({'labels': labels, 'scores': predictions},'./evaluations/'+args.models+'.pth')

