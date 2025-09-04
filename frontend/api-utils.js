/**
 * Unified API Response Handling Utilities
 */

class ApiResponse {
    /**
     * Handle API response
     * @param {Object} response - API response object
     * @param {Function} onSuccess - Success callback function, receives data parameter
     * @param {Function} onError - Error callback function, receives message parameter
     */
    static handle(response, onSuccess, onError) {
        if (response.code === 0) {
            // Success response
            if (typeof onSuccess === 'function') {
                onSuccess(response.data || {});
            }
        } else {
            // Error response
            if (typeof onError === 'function') {
                onError(response.message || 'Unknown error');
            } else {
                // Default error handling: display error message
                console.error('API Error:', response.message);
                if (typeof showMessage === 'function') {
                    showMessage(response.message, 'error');
                } else {
                    alert(response.message);
                }
            }
        }
    }

    /**
     * Check if response is successful
     * @param {Object} response - API response object
     * @returns {boolean} - Whether successful
     */
    static isSuccess(response) {
        return response && response.code === 0;
    }

    /**
     * Get response data
     * @param {Object} response - API response object
     * @returns {*} - Response data
     */
    static getData(response) {
        return response && response.code === 0 ? response.data : null;
    }

    /**
     * Get error message
     * @param {Object} response - API response object
     * @returns {string} - Error message
     */
    static getErrorMessage(response) {
        return response && response.code !== 0 ? response.message : null;
    }

    /**
     * Create success response
     * @param {*} data - Response data
     * @param {string} message - Optional message
     * @returns {Object} - Response object
     */
    static success(data = {}, message = null) {
        return {
            code: 0,
            message: message,
            data: data
        };
    }

    /**
     * Create error response
     * @param {string} message - Error message
     * @param {*} data - Optional data
     * @returns {Object} - Response object
     */
    static error(message, data = null) {
        return {
            code: -1,
            message: message,
            data: data
        };
    }
}

/**
 * Encapsulated fetch requests with automatic response format handling
 */
class ApiClient {
    /**
     * Send GET request
     * @param {string} url - Request URL
     * @param {Object} options - Request options
     * @returns {Promise<Object>} - Response object
     */
    static async get(url, options = {}) {
        try {
            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error('API request failed:', error);
            return ApiResponse.error(error.message);
        }
    }

    /**
     * Send POST request
     * @param {string} url - Request URL
     * @param {*} data - Request data
     * @param {Object} options - Request options
     * @returns {Promise<Object>} - Response object
     */
    static async post(url, data = null, options = {}) {
        try {
            const isFormData = data instanceof FormData;
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    ...(isFormData ? {} : {'Content-Type': 'application/json'}),
                    ...options.headers
                },
                body: isFormData ? data : JSON.stringify(data),
                ...options
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error('API request failed:', error);
            return ApiResponse.error(error.message);
        }
    }

    /**
     * Send PUT request
     * @param {string} url - Request URL
     * @param {*} data - Request data
     * @param {Object} options - Request options
     * @returns {Promise<Object>} - Response object
     */
    static async put(url, data = null, options = {}) {
        try {
            const isFormData = data instanceof FormData;
            const response = await fetch(url, {
                method: 'PUT',
                headers: {
                    ...(isFormData ? {} : {'Content-Type': 'application/json'}),
                    ...options.headers
                },
                body: isFormData ? data : JSON.stringify(data),
                ...options
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error('API request failed:', error);
            return ApiResponse.error(error.message);
        }
    }

    /**
     * Send DELETE request
     * @param {string} url - Request URL
     * @param {Object} options - Request options
     * @returns {Promise<Object>} - Response object
     */
    static async delete(url, options = {}) {
        try {
            const response = await fetch(url, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error('API request failed:', error);
            return ApiResponse.error(error.message);
        }
    }
}

// Export to global scope
window.ApiResponse = ApiResponse;
window.ApiClient = ApiClient;
