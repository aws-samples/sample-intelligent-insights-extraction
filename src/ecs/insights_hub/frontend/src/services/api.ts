import axios from 'axios';

// Define interfaces for our data types
export interface Design {
  id: string;
  title: string;
  description: string;
  imageUrl: string;
  tags: string[];
}

export interface DesignDetail extends Design {
  content: string;
  source: string;
  relatedImages: string[];
}

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:3001';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const getDesigns = async (params = {}): Promise<Design[]> => {
  try {
    const response = await api.get('/api/designs', { params });
    return response.data;
  } catch (error) {
    console.error('Error fetching designs:', error);
    throw error;
  }
};

export const getDesignById = async (id: string): Promise<DesignDetail> => {
  try {
    const response = await api.get(`/designs/${id}`);
    return response.data;
  } catch (error) {
    console.error(`Error fetching design with id ${id}:`, error);
    throw error;
  }
};

export const searchDesigns = async (query: string): Promise<Design[]> => {
  try {
    const response = await api.get('/designs/search', { params: { query } });
    return response.data;
  } catch (error) {
    console.error('Error searching designs:', error);
    throw error;
  }
};

export default api;
