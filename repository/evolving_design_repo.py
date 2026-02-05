"""
UMACAD - Evolving Design Repository (EDR)
Production Version: Connects to pre-ingested ChromaDB "Long Term Memory"
"""

import chromadb
import uuid
from typing import List, Dict, Any, Optional
from loguru import logger

class EvolvingDesignRepository:
    """
    The Brain Interface.
    Connects the Agents to the Massive Vector Database (ChromaDB).
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.db_path = "./repository/chroma_db"
        
        self.client = None
        self.coll_patterns = None
        self.coll_code = None
        
        try:
            # 1. Connect to the existing database
            self.client = chromadb.PersistentClient(path=self.db_path)
            
            # 2. Link to the collections (Planning Brain)
            try:
                self.coll_patterns = self.client.get_collection("design_patterns")
                logger.info("  - Linked 'design_patterns' (Planning Brain)")
            except Exception:
                logger.warning("  ! Could not find 'design_patterns'.")

            # 3. Link to the collections (Coding Brain)
            try:
                self.coll_code = self.client.get_collection("code_examples")
                logger.info("  - Linked 'code_examples' (Coding Brain)")
            except Exception:
                logger.warning("  ! Could not find 'code_examples'.")

            logger.info(f"✅ EDR successfully connected to Long-Term Memory at {self.db_path}")

        except Exception as e:
            logger.error(f"❌ Critical DB Error: {e}")

    def search_patterns(self, search_terms: List[str]) -> List[Dict[str, Any]]:
        """
        Used by Project Manager.
        Searches the Planning Dataset for similar past strategies.
        """
        if not self.coll_patterns:
            return []
            
        try:
            query = " ".join(search_terms)
            
            results = self.coll_patterns.query(
                query_texts=[query], 
                n_results=3 
            )
            
            output = []
            
            documents = results.get('documents')
            metadatas = results.get('metadatas')

            if documents is not None and metadatas is not None:
                doc_list = documents[0]
                meta_list = metadatas[0]

                for i, doc in enumerate(doc_list):
                    meta = meta_list[i]
                    output.append({
                        "plan_logic": doc,
                        "user_request": meta.get('user_request', 'Fetched from DB'),
                        "technical_name": meta.get('technical_name', 'Unknown Object'),
                        "tags": str(meta.get('tags', '')).split(',')
                    })
            
            return output
            
        except Exception as e:
            logger.error(f"Pattern Search failed: {e}")
            return []

    def get_code_examples(self, task_type: str) -> List[str]:
        """
        Used by Design Architect.
        Searches the Code Dataset for implementation patterns.
        """
        if not self.coll_code:
            return []
            
        try:
            results = self.coll_code.query(
                query_texts=[task_type], 
                n_results=3 
            )
            
            code_snippets = []
            
            documents = results.get('documents')
            metadatas = results.get('metadatas')

            if documents is not None and metadatas is not None:
                doc_list = documents[0]
                meta_list = metadatas[0]
                
                for i, _ in enumerate(doc_list):
                    code = meta_list[i].get('code')
                    if code:
                        code_snippets.append(code)
                        logger.debug(f"Retrieved code example {i+1} for task '{task_type}'")
                        
            return code_snippets
            
        except Exception as e:
            logger.error(f"Code Search failed: {e}")
            return []
            
    def archive_successful_design(self, design_brief, construction_plan, final_code, metadata) -> None:
        """
        Self-Learning: Saves new successful designs back into BOTH parts of the brain.
        """
        success_count = 0
        unique_suffix = str(uuid.uuid4())[:8]
        session_id = metadata.get('session_id', 'unknown')
        
        # 1. Archive the CODE
        if self.coll_code:
            try:
                archive_id = f"archive_code_{session_id}_{unique_suffix}"
                self.coll_code.add(
                    documents=[design_brief.design_description],
                    metadatas=[{
                        "code": final_code,
                        "source": "self_learning_archive",
                        "keywords": ", ".join(design_brief.tags)
                    }],
                    ids=[archive_id]
                )
                success_count += 1
            except Exception as e:
                logger.warning(f"Could not archive Code: {e}")

        # 2. Archive the PLAN
        if self.coll_patterns:
            try:
                archive_id = f"archive_plan_{session_id}_{unique_suffix}"
                
                plan_text = f"Strategy: {construction_plan.strategy}\nSteps:\n"
                for task in construction_plan.tasks:
                    plan_text += f"{task.step_number}. {task.description}\n"

                self.coll_patterns.add(
                    documents=[plan_text],
                    metadatas=[{
                        "user_request": design_brief.user_input_text,
                        "technical_name": design_brief.design_title,
                        "tags": ", ".join(design_brief.tags),
                        "design_type": design_brief.design_category,
                        "complexity": "proven_success",
                        "verification_steps": "Verified by UMACAD System",
                        "operations": "automated_generation"
                    }],
                    ids=[archive_id]
                )
                success_count += 1
            except Exception as e:
                logger.warning(f"Could not archive Plan: {e}")

        if success_count > 0:
            logger.info(f"🧠 Learned new design! Archived '{design_brief.design_title}' to Long-Term Memory.")