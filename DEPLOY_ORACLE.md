# NeuroLab - Oracle Cloud Free Tier Deployment

## Step 1: Create Account & VM

1. **Sign up**: https://signup.cloud.oracle.com/
   - Enter email, password, **credit card** (1-2 EGP hold, refunded)
   - Choose region close to Egypt: **EU Frankfurt** or **UK South**
2. **Create VM**: Compute -> Instances -> Create Instance
   - Name: `neuro-lab` | Image: **Canonical Ubuntu 22.04** | Shape: **VM.Standard.A1.Flex** (4 OCPU / 24 GB)
   - Add SSH key (Generate or paste yours)
   - Boot volume: **200 GB**
3. **Note your public IP** (shown in instance details)

## Step 2: Upload Project Files

From your laptop, upload the whole NeuroLab folder:

```bash
# ZIP first (exclude venv + node_modules)
# Then upload:
scp -i ~/Downloads/ssh-key-rsa.key -r ./NeuroLab ubuntu@<SERVER_IP>:/home/ubuntu/neurolab
```

Or use WinSCP, FileZilla, or Cyberduck (SFTP).

## Step 3: SSH & Deploy

```bash
ssh -i ~/Downloads/ssh-key-rsa.key ubuntu@<SERVER_IP>
cd ~/neurolab
chmod +x deploy.sh
./deploy.sh     # takes 3-5 minutes
```

## Step 4: Open Firewall

1. OCI Console -> Networking -> Virtual Cloud Networks
2. Click your VCN -> Security Lists -> Default Security List
3. **Add Ingress Rule**: Source=`0.0.0.0/0`, Protocol=`TCP`, Port=`8000`

## Step 5: Access from Anywhere

```
http://<SERVER_IP>:8000
```

Frontend + API same URL. Works from iPad, phone, laptop.

## Useful Commands

| Command | Purpose |
|---------|---------|
| `sudo systemctl status neurolab` | Check if running |
| `journalctl -u neurolab -f` | Live logs |
| `sudo systemctl restart neurolab` | Restart server |
| `cd ~/neurolab/backend && source venv/bin/activate` | Manual Python env |

## Troubleshooting

- **Port 8000 not reachable**: Check Oracle Cloud security list ingress rule
- **Model download fails**: Run `curl -L -o backend/models/pose_landmarker_heavy.task https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task`
- **Out of memory**: Run `sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile` to add swap
