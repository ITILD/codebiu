import { exec } from 'child_process';
import os from 'os';

const killPort = (port: string): Promise<void> => {
  return new Promise((resolve, reject) => {
    const platform: NodeJS.Platform = os.platform();

    if (platform === 'win32') {
      // Windows
      exec(`netstat -ano | findstr :${port}`, (error: Error | null, stdout: string, stderr: string) => {
        if (error) {
          console.error(`Not find process on port ${port}:`, error.message);
          return resolve();
        }

        if (stderr) {
          console.error(`stderr: ${stderr}`);
          return resolve();
        }

        if (stdout) {
          const parts: string[] = stdout.trim().split(/\s+/);
          const pid: string = parts[4];

          if (pid) {
            exec(`taskkill /PID ${pid} /F`, (killError: Error | null) => {
              if (killError) {
                console.error(`Failed to kill process ${pid}:`, killError.message);
              } else {
                console.log(`Successfully killed process ${pid} on port ${port}`);
              }
              resolve();
            });
          } else {
            resolve();
          }
        } else {
          resolve();
        }
      });
    } else {
      // Linux/Mac - 更健壮的实现
      exec(`lsof -ti:${port}`, (error: Error | null, stdout: string, stderr: string) => {
        if (error) {
          if (error.message.includes('no process found')) {
            console.log(`No process found on port ${port}`);
            return resolve();
          }
          console.error(`Error finding process on port ${port}:`, error.message);
          return resolve();
        }

        if (stderr) {
          console.error(`stderr: ${stderr}`);
          return resolve();
        }

        const pids = stdout.trim().split('\n').filter(pid => pid.trim() !== '');
        
        if (pids.length === 0) {
          console.log(`No process found on port ${port}`);
          return resolve();
        }

        exec(`kill -9 ${pids.join(' ')}`, (killError: Error | null) => {
          if (killError) {
            console.error(`Failed to kill processes:`, killError.message);
          } else {
            console.log(`Successfully killed processes ${pids.join(', ')} on port ${port}`);
          }
          resolve();
        });
      });
    }
  });
};

export { killPort };