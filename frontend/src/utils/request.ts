import axios from "axios";
import type { AxiosInstance, AxiosRequestConfig, AxiosResponse } from "axios";
import { ElMessageBox, ElMessage } from "element-plus";
import { useUserStore } from "@/store/user";

// 响应数据接口
export interface ApiResponse<T = any> {
  code: number;
  message?: string;
  data?: T;
  [key: string]: any;
}

class HttpClient {
  private instance: AxiosInstance;

  constructor(config?: AxiosRequestConfig) {
    this.instance = axios.create({
      baseURL: import.meta.env.VITE_APP_BASE_API,
      timeout: 5000,
      ...config
    });

    this.setupInterceptors();
  }

  private setupInterceptors(): void {
    // 请求拦截器
    this.instance.interceptors.request.use(
      (config) => {
        // 如果需要token认证，可以在这里添加
        // const userStore = useUserStore();
        // if (userStore.token) {
        //   (config.headers as any)['X-Token'] = userStore.token;
        // }
        return config;
      },
      (error) => {
        console.error("请求错误:", error);
        return Promise.reject(error);
      }
    );

    // 响应拦截器
    this.instance.interceptors.response.use(
      (response: AxiosResponse): Promise<AxiosResponse<any>> | AxiosResponse => {
        const res = response.data as ApiResponse;

        // 如果返回的状态码不是20000，表示发生了错误
        if (res.code !== 20000) {
          ElMessage.error(res.message || "请求失败");

          // 处理特殊错误码
          if ([50008, 50012, 50014].includes(res.code)) {
            // 重新登录
            ElMessageBox.confirm(
              "您已登出，可以取消继续留在该页面，或者重新登录",
              "确认登出",
              {
                confirmButtonText: "重新登录",
                cancelButtonText: "取消",
                type: "warning"
              }
            ).then(() => {
              // 动态获取userStore实例
              const userStore = useUserStore();
              userStore.resetToken().then(() => {
                location.reload();
              });
            });
          }
          
          return Promise.reject(new Error(res.message || "请求错误"));
        }
        
        // 返回正确的结果，包装成AxiosResponse格式
        return {
          data: res,
          status: 200,
          statusText: 'OK',
          headers: response.headers,
          config: response.config
        };
      },
      (error) => {
        console.error("响应错误:", error);
        ElMessage.error(error.message || "请求失败");
        return Promise.reject(error);
      }
    );
  }

  // 封装 GET 请求
  public get<T = any>(url: string, config?: AxiosRequestConfig): Promise<ApiResponse<T>> {
    return this.instance.get(url, config).then(res => res.data);
  }

  // 封装 POST 请求 - 添加请求体泛型 D
  public post<T = any, D = any>(
    url: string, 
    data?: D, 
    config?: AxiosRequestConfig
  ): Promise<ApiResponse<T>> {
    return this.instance.post(url, data, config).then(res => res.data);
  }

  // 封装 PUT 请求 - 添加请求体泛型 D
  public put<T = any, D = any>(
    url: string, 
    data?: D, 
    config?: AxiosRequestConfig
  ): Promise<ApiResponse<T>> {
    return this.instance.put(url, data, config).then(res => res.data);
  }

  // 封装 PATCH 请求 - 新增，通常用于部分更新
  public patch<T = any, D = any>(
    url: string, 
    data?: D, 
    config?: AxiosRequestConfig
  ): Promise<ApiResponse<T>> {
    return this.instance.patch(url, data, config).then(res => res.data);
  }

  // 封装 DELETE 请求
  public delete<T = any>(url: string, config?: AxiosRequestConfig): Promise<ApiResponse<T>> {
    return this.instance.delete(url, config).then(res => res.data);
  }

  // 封装文件上传请求
  public upload<T = any>(
    url: string,
    formData: FormData,
    config?: AxiosRequestConfig
  ): Promise<ApiResponse<T>> {
    return this.instance.post(url, formData, {
      ...config,
      headers: {
        'Content-Type': 'multipart/form-data',
        ...config?.headers,
      },
    }).then(res => res.data);
  }
}

// 创建默认实例
const httpClient = new HttpClient();

export default httpClient;